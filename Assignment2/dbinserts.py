from main import app, db, Orders

order1 = Orders(customer_id="cust_002", item_id="item_002", quantity=3)

with app.app_context():
    db.session.add(order1)
    db.session.commit()
