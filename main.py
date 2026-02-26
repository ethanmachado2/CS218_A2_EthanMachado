import datetime as dt
import uuid
import hashlib
import json
from flask import Flask, jsonify, request, make_response, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
from marshmallow import Schema, fields, validate, ValidationError

app = Flask(__name__)

# function that returns the current date and time for timestamp purposes

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

# function that generates a randomized id for requests

def new_id():
    return uuid.uuid4().hex



def canonical_json_bytes(payload: dict) -> bytes:
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

# database creation

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ordersmgmt.db"

db = SQLAlchemy(app)

# orders database table model creation

class Orders(db.Model):
    __tablename__ = "orders"
    order_id  = db.Column(db.Integer, primary_key = True) #, default = new_id)
    status = db.Column(db.String, nullable = False, default = "created")
    customer_id = db.Column(db.String, nullable = False)
    item_id = db.Column(db.String, nullable = False)
    quantity = db.Column(db.Integer, nullable = False)
    created = db.Column(db.DateTime, nullable = False, default = utcnow)
    updated = db.Column(db.DateTime, nullable = False, default = utcnow, onupdate = utcnow)
    ledger_entries = relationship("Ledger", back_populates="order", cascade="all, delete-orphan")

# function to return a record from the orders table as a dictionary for future use

    # def to_dict(self):
    #     return {
    #         "order_id" : self.order_id,
    #         "status" : self.status,
    #         "customer_id" : self.customer_id,
    #         "item_id" : self.item_id,
    #         "quantity" : self.quantity,
    #         "created" : self.created,
    #         "updated" : self.updated
    #     }

# ledger database table model creation that is related to the orders table

class Ledger(db.Model):
    __tablename__ = "ledger"
    __table_args__ = (
        UniqueConstraint("order_id", name = "unique_order_id"),
    )
    ledger_id  = db.Column(db.String, primary_key = True, default = new_id)
    order_id = db.Column(db.Integer, ForeignKey("orders.order_id"), nullable = False)
    created = db.Column(db.DateTime, nullable = False, default = utcnow)
    order = relationship("Orders", back_populates="ledger_entries")

# function to return a record from the ledger table as a dictionary for future use

    # def to_dict(self):
    #     return {
    #         "ledger_id" : self.ledger_id,
    #         "order_id" : self.order_id,
    #         "created" : self.created
    #     }

# idempotency_records database table model creation
    
class Idempotency(db.Model):
    __tablename__ = "idempotency_records"
    idem_key  = db.Column(db.String, primary_key = True)
    req_id = db.Column(db.String, nullable = False)
    req_status = db.Column(db.String, nullable = False, default = "in_process")
    req_hash = db.Column(db.String, nullable = False)
    req_response = db.Column(db.Text, nullable = True)
    req_code = db.Column(db.Integer, nullable = True)
    timestamp = db.Column(db.DateTime, nullable = False, default = utcnow)

# function to return a record from the idempotency_records table as a dictionary for future use

    # def to_dict(self):
    #     return {
    #         "idem_key" : self.idem_key,
    #         "req_id" : self.req_id
    #         "req_status" : self.req_status,
    #         "req_hash" : self.req_hash,
    #         "req_response" : self.req_response,
    #         "req_code" : self.req_code,
    #         "timestamp" : self.timestamp
    #     }

# creation of database instance

with app.app_context():
    db.create_all()

# creation of a client request schema for request body validation

class OrderSchema(Schema):
    customer_id = fields.Str(required = True, validate = validate.Length(min = 1))
    item_id = fields.Str(required = True, validate = validate.Length(min = 1))
    quantity = fields.Int(required = True, validate = validate.Range(min = 1))

order_schema = OrderSchema()

# creation of Routes (API endpoints)
# "/" default route with information on other endpoints

@app.route("/")
def home():
    return jsonify({"message" : "/orders endpoint for order creation. /orders/<order_id> endpoint for order display."})

# main order processing endpoint that processes client order creation requests

@app.route("/orders", methods = ["POST"])
def orders_route():
    # generation of unique request ID
    g.uniq_req_id = new_id()
    # getting the Idempotency-Key from the request header
    idempotency_key = request.headers.get("Idempotency-Key")
    # debug header created for testing commit without response failure scenario
    fail_after_commit = request.headers.get("X-Debug-Fail-After-Commit") == "true"
    # check to determine if client requets contains an Idempotency-Key in its header
    if not idempotency_key:
         return make_response(jsonify({"Error" : "Missing Idempotency-Key"}), 400)
    # parsing of JSON request data
    json_req = request.get_json(silent = True)
    # checks for invalid client request based on request body data validation
    try:
        req_body = order_schema.load(json_req)
    except ValidationError as e:
        return make_response(jsonify({"Error" : "Invalid data", "Messages" : e.messages}), 422)
    # returns HTTP 400 message if request body is not a valid python dictionary object
    if not isinstance(req_body, dict):
        return make_response(jsonify({"Error" : "Invalid JSON body"}), 400)

    # creating a request body hash (fingerprint)
    req_hash = sha256_hex(canonical_json_bytes(req_body))

    # if the request is determined to be valid, then the order creation process begins
    try:
        # gets the first client request to avoid race conditions
        get_key = Idempotency.query.filter_by(idem_key = idempotency_key).first()

        # checks if Idempotency-Key value already exists in idempotency_records table
        if get_key:
            # if Idempotency-Key value already exists with different fingerprint, return 409 conflict
            if get_key.req_hash != req_hash:
                # db.session.rollback() -- rollback not needed here, done later on in process
                return make_response(jsonify({"Error" : "Existing Idempotency-Key with different payload."}), 409)
            # if Idempotency-Key value already exists with completed status, return original request response and status code
            if get_key.req_status == "completed":
                response = make_response(json.loads(get_key.req_response), get_key.req_code)
                response.headers["X-Request-ID"] = g.uniq_req_id
                return response
            # if # if Idempotency-Key value already exists with in_process status, return 409 conflict
            if get_key.req_status == "in_process":
                # db.session.rollback() -- rollback not needed here, done later on in process
                return make_response(jsonify({"Error" : "Request in process"}), 409)

        # if # if Idempotency-Key value does not exist, add Idempotency-Key record to idempotency_records table
        if not get_key:
            get_key = Idempotency(
                idem_key = idempotency_key,
                req_id = g.uniq_req_id,
                req_status = "in_process",
                req_hash = req_hash
                )
            db.session.add(get_key)
            # check if Idempotency-Key value is being handled by a different thread
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                return make_response(jsonify({"Error" : "Conflict: Idempotency-Key was just logged by another thread"}), 409)
    
        # creation of orders table entry
        order_creation = Orders(
            customer_id = req_body.get("customer_id"),
            item_id = req_body.get("item_id"),
            quantity = req_body.get("quantity")
        )
        db.session.add(order_creation)
        db.session.flush()

        # creation of ledger table entry associated with order
        ledger_entry = Ledger(
            order_id = order_creation.order_id,
        )
        db.session.add(ledger_entry)
    
        # generate response body for successful order creation
        response_body = {"order_id" : order_creation.order_id, "status" : "created"}

        # set response code to 201, set response body, and set status to completed in idempotency_records table
        get_key.req_code = 201
        get_key.req_response = json.dumps(response_body)
        get_key.req_status = "completed"

        # commit idempotency_records, order, and ledger table entries at once
        db.session.commit()

        # exception raised if debug header is maintained in client request
        if fail_after_commit:
            raise Exception("Simulated Failure: Data commited but no response sent")

        # return 201 created status code with response body if order is created successfully
        end_response = make_response(jsonify(response_body), 201)
        end_response.headers["X-Request-ID"] = g.uniq_req_id
        return end_response

    
    # exception raised with rollback in case of an error
    except Exception as e:
        db.session.rollback()
        error_response = make_response(jsonify({"Error" : str(e)}), 500)
        error_response.headers["X-Request-ID"] = g.uniq_req_id
        return error_response

# simple GET order endpoint that is searchable via {order_id}.
# return 404 not found status code if {order_id} is not maintained in orders table
@app.route("/orders/<id>", methods = ["GET"])
def get_order(id):
        order = Orders.query.get(id)
        if order:
            return jsonify({"order_id" : order.order_id, "customer_id" : order.customer_id, "item_id" : order.item_id, "quantity" : order.quantity})
        return (jsonify({"Error" : "Order not found"}), 404)


if __name__ == "__main__":
    app.run(debug = True)