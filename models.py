# this file defines the database structure for the boutique system
# it uses 4 tables to handle inventory, sales, and stock audits

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# table 1: users - for secure login (objective 1.3.2-I)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False) # stored as a secure hash

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# table 2: products - stores item details and prices (objective 1.3.2-II)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    cost_price = db.Column(db.Float, nullable=False)     # buying price from suppliers
    selling_price = db.Column(db.Float, nullable=False)  # price for customers
    stock_quantity = db.Column(db.Integer, default=0)    # physical units on hand
    min_stock_level = db.Column(db.Integer, default=5)   # for low stock flagging (objective 1.3.2-V)
    
    def __repr__(self):
        return f'<Product {self.name}>'

# table 3: sales - tracks every transaction and calculates profit (objective 1.3.2-III & IV)
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_revenue = db.Column(db.Float, nullable=False) # qty * selling_price
    total_cost = db.Column(db.Float, nullable=False)    # qty * cost_price
    total_profit = db.Column(db.Float, nullable=False)  # revenue - cost
    sale_date = db.Column(db.DateTime, default=datetime.utcnow) # date/time of sale
    
    # links the sale back to the product name
    product = db.relationship('Product', backref=db.backref('sales', lazy=True))

# table 4: stock audit - identifies theft or missing items (objective 1.3.2-V & requirement 1.4)
class StockAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    system_stock = db.Column(db.Integer, nullable=False)   # what the computer says
    physical_count = db.Column(db.Integer, nullable=False)  # what the owner counts on shelf
    discrepancy = db.Column(db.Integer, nullable=False)     # difference (missing items)
    audit_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(500))
    
    product = db.relationship('Product', backref=db.backref('audits', lazy=True))
