import datetime as dt
import uuid
import hashlib
import json
from flask import Flask, jsonify, request, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
from marshmallow import Schema, fields, validate, ValidationError

app = Flask(__name__)

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def new_id():
    return uuid.uuid4().hex

def canonical_json_bytes(payload: dict) -> bytes:
    # Stable JSON fingerprint (sorted keys, no whitespace)
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

# Create Database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ordersmgmt.db"

db = SQLAlchemy(app)

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

    def to_dict(self):
        return {
            "order_id" : self.order_id,
            "status" : self.status,
            "customer_id" : self.customer_id,
            "item_id" : self.item_id,
            "quantity" : self.quantity,
            "created" : self.created,
            "updated" : self.updated
        }
    
class Ledger(db.Model):
    __tablename__ = "ledger"
    __table_args__ = (
        UniqueConstraint("order_id", name = "unique_order_id"),
    )
    ledger_id  = db.Column(db.String, primary_key = True, default = new_id)
    order_id = db.Column(db.Integer, ForeignKey("orders.order_id"), nullable = False)
    created = db.Column(db.DateTime, nullable = False, default = utcnow)
    order = relationship("Orders", back_populates="ledger_entries")

    def to_dict(self):
        return {
            "ledger_id" : self.ledger_id,
            "order_id" : self.order_id,
            "created" : self.created
        }
    
class Idempotency(db.Model):
    __tablename__ = "idempotency_records"
    idem_key  = db.Column(db.String, primary_key = True)
    req_status = db.Column(db.String, nullable = False, default = "in_process")
    req_hash = db.Column(db.String, nullable = False)
    req_response = db.Column(db.Text, nullable = True)
    req_code = db.Column(db.Integer, nullable = True)
    timestamp = db.Column(db.DateTime, nullable = False, default = utcnow)

    def to_dict(self):
        return {
            "idem_key" : self.idem_key,
            "req_status" : self.req_status,
            "req_hash" : self.req_hash,
            "req_response" : self.req_response,
            "req_code" : self.req_code,
            "timestamp" : self.timestamp
        }

with app.app_context():
    db.create_all()

class OrderSchema(Schema):
    customer_id = fields.Str(required = True, validate = validate.Length(min = 1))
    item_id = fields.Str(required = True, validate = validate.Length(min = 1))
    quantity = fields.Int(required = True, validate = validate.Range(min = 1))

order_schema = OrderSchema()

# Create Routes
@app.route("/")
def home():
    return jsonify({"message" : "/orders endpoint for order creation. /orders/<order_id> endpoint for order display."})

@app.route("/orders", methods = ["POST"])
def orders_route():
    # body = request.get_json(silent=True)
    idempotency_key = request.headers.get("Idempotency-Key")

    fail_after_commit = request.headers.get("X-Debug-Fail-After-Commit") == "true"

    if not idempotency_key:
         return make_response(jsonify({"Error" : "Missing Idempotency-Key"}), 400)
    
    json_req = request.get_json(silent = True)
    try:
        req_body = order_schema.load(json_req)
    except ValidationError as e:
        return make_response(jsonify({"Error" : "Invalid data", "Messages" : e.messages}), 422)
    # req_body = request.get_json(silent = True)

    if not isinstance(req_body, dict):
        return make_response(jsonify({"Error" : "Invalid JSON body"}), 400)
    
    # customer_id = req_body.get("customer_id")
    # item_id = req_body.get("item_id")
    # quantity = req_body.get("quantity")

    req_hash = sha256_hex(canonical_json_bytes(req_body))

    try:

        get_key = Idempotency.query.filter_by(idem_key = idempotency_key).first()

        if get_key:
            if get_key.req_hash != req_hash:
                # db.session.rollback()
                return make_response(jsonify({"Error" : "Existing Idempotency-Key with different payload."}), 409)
            
            if get_key.req_status == "completed":
                return make_response(json.loads(get_key.req_response), get_key.req_code)
            
            if get_key.req_status == "in_process":
                # db.session.rollback()
                return make_response(jsonify({"Error" : "Request in process"}), 409)

    # try:
        if not get_key:
            get_key = Idempotency(
                idem_key = idempotency_key,
                req_status = "in_process",
                req_hash = req_hash
                # timestamp = utcnow(),
                )
            db.session.add(get_key)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                return make_response(jsonify({"Error" : "Conflict: Key was just logged by another thread"}), 409)

        
        # return {"Idempotency-Key" : get_key.idem_key}
    
        order_creation = Orders(
            customer_id = req_body.get("customer_id"),
            item_id = req_body.get("item_id"),
            quantity = req_body.get("quantity")
            # status = "created",
        )
        db.session.add(order_creation)
        db.session.flush()

        ledger_entry = Ledger(
            order_id = order_creation.order_id,
        )
        db.session.add(ledger_entry)
    
        response_body = {"order_id" : order_creation.order_id, "status" : "created"}

        get_key.req_code = 201
        get_key.req_response = json.dumps(response_body)
        get_key.req_status = "completed"

        db.session.commit()
        # db.session.close()

        if fail_after_commit:
            raise Exception("Simulated Failure: Data commited but no response sent")

        return make_response(jsonify(response_body), 201)
    
    except Exception as e:
        db.session.rollback()
        return make_response(jsonify({"Error" : str(e)}), 500)

@app.route("/orders/<id>", methods = ["GET"])
def get_order(id):
        order = Orders.query.get(id)
        if order:
            return jsonify({"order_id" : order.order_id, "customer_id" : order.customer_id, "item_id" : order.item_id, "quantity" : order.quantity})
        return (jsonify({"Error" : "Order not found"}), 404)


if __name__ == "__main__":
    app.run(debug = True)