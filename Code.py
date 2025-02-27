# Install required packages
# Run this in Replit terminal: pip install flask flask-sqlalchemy stripe twilio flask-mail
flask
gunicorn
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import stripe
import os
from twilio.rest import Client
from flask_mail import Mail, Message
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Server is running!"

# Database Setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Stripe API Key (Replace with your own)
stripe.api_key = "your_stripe_secret_key"

# Twilio API (Replace with your own)
TWILIO_SID = "your_twilio_sid"
TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
TWILIO_PHONE_NUMBER = "your_twilio_phone_number"
twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# Email Setup (Replace with your own SMTP settings)
app.config['MAIL_SERVER'] = 'smtp.yourmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'your_email@example.com'
app.config['MAIL_PASSWORD'] = 'your_email_password'
app.config['MAIL_USE_TLS'] = True
mail = Mail(app)

# Order Model
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100))
    service_type = db.Column(db.String(100))
    address = db.Column(db.String(200))
    status = db.Column(db.String(50), default="Order Received")
    payment_status = db.Column(db.String(50), default="Pending")

# Create the database
with app.app_context():
    db.create_all()

# Create Order Endpoint
@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.json
    new_order = Order(
        customer_name=data['customer_name'],
        service_type=data['service_type'],
        address=data['address']
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({"message": "Order placed successfully!", "order_id": new_order.id})

# Update Order Status
@app.route('/update_order/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    data = request.json
    order.status = data['status']
    db.session.commit()

    # Send notifications only if contact info is provided
    if 'customer_phone' in data:
        twilio_client.messages.create(
            body=f"Your order status has been updated to: {order.status}",
            from_=TWILIO_PHONE_NUMBER,
            to=data['customer_phone']
        )

    if 'customer_email' in data:
        msg = Message(
            subject="Order Status Update",
            sender=app.config['MAIL_USERNAME'],
            recipients=[data['customer_email']],
            body=f"Your order status has been updated to: {order.status}"
        )
        mail.send(msg)

    return jsonify({"message": "Order status updated successfully!"})

# Payment Processing
@app.route('/pay', methods=['POST'])
def process_payment():
    if not request.is_json:
        return jsonify({"error": "Content type must be application/json"}), 400
    
    data = request.json
    required_fields = ['amount', 'token', 'order_id']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
        
    try:
        charge = stripe.Charge.create(
            amount=int(float(data['amount']) * 100),  # Convert dollars to cents
            currency="usd",
            source=data['token'],  # Get Stripe token from frontend
            description=f"Payment for Order ID {data['order_id']}"
        )
        order = Order.query.get(data['order_id'])
        order.payment_status = "Paid"
        db.session.commit()
        return jsonify({"message": "Payment successful!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Get Order Status
@app.route('/order_status/<int:order_id>', methods=['GET'])
def get_order_status(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify({"order_id": order.id, "status": order.status, "payment_status": order.payment_status})

# Use environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
port = int(os.getenv("PORT", 10000))  # Default to 10000 if not set

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
