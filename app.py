# app.py - handles system logic and routing
# run this file starting the server: python app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Product, Sale, StockAudit
import os
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///boutique.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'nairobi-boutique-secure-key'

db.init_app(app)

# login manager setup (objective 1.3.2-I)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# setup database and default data
with app.app_context():
    db.create_all()
    
    # ensure Maureen exists with correct password
    maureen = User.query.filter_by(username='Maureen').first()
    if not maureen:
        maureen = User(username='Maureen')
        maureen.set_password('manage200')
        db.session.add(maureen)
    else:
        maureen.set_password('manage200') # force update password in case of typo
    db.session.commit()
    
    # starter stock categories for a boutique
    if Product.query.count() == 0:
        samples = [
            Product(name='Matte Red Lipstick', category='Cosmetics', cost_price=450, selling_price=800, stock_quantity=20, min_stock_level=5),
            Product(name='Luxury Oud Perfume', category='Fragrance', cost_price=2500, selling_price=4500, stock_quantity=3, min_stock_level=5),
            Product(name='Gold Plated Necklace', category='Jewelry', cost_price=1200, selling_price=2500, stock_quantity=10, min_stock_level=3)
        ]
        db.session.bulk_save_objects(samples)
        db.session.commit()

# login and logout 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# main dashboard - generates profit reports (objective 1.3.2-IV)
@app.route('/')
@login_required
def index():
    # calculate total revenue and total profit from all sales records
    total_revenue = db.session.query(db.func.sum(Sale.total_revenue)).scalar() or 0
    total_profit = db.session.query(db.func.sum(Sale.total_profit)).scalar() or 0
    
    # identify low-stock items (objective 1.3.2-V)
    low_stock = Product.query.filter(Product.stock_quantity <= Product.min_stock_level).count()
    
    # daily profit report logic
    today = date.today()
    today_profit = db.session.query(db.func.sum(Sale.total_profit)).filter(db.func.date(Sale.sale_date) == today).scalar() or 0
    
    latest_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    return render_template('index.html', rev=total_revenue, prof=total_profit, low=low_stock, today_p=today_profit, sales=latest_sales)

# view current stock levels (functional requirement 1.4)
@app.route('/inventory')
@login_required
def inventory():
    items = Product.query.all()
    return render_template('inventory.html', items=items)

# add new product (objective 1.3.2-II)
@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        new_item = Product(
            name=request.form.get('name'),
            category=request.form.get('category'),
            cost_price=float(request.form.get('cost')),
            selling_price=float(request.form.get('price')),
            stock_quantity=int(request.form.get('stock')),
            min_stock_level=int(request.form.get('min_level'))
        )
        db.session.add(new_item)
        db.session.commit()
        flash('New item added to stock!', 'success')
        return redirect(url_for('inventory'))
    return render_template('add_product.html')

# edit item details (update functionality)
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        product.cost_price = float(request.form.get('cost')),
        product.selling_price = float(request.form.get('price')),
        product.stock_quantity = int(request.form.get('stock')),
        product.min_stock_level = int(request.form.get('min_level'))
        db.session.commit()
        flash(f'Changes saved for {product.name}', 'success')
        return redirect(url_for('inventory'))
    return render_template('edit_product.html', item=product)

# remove product from system (delete functionality)
@app.route('/delete_product/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    name = product.name
    db.session.delete(product) 
    db.session.commit()
    flash(f'{name} deleted from the list.', 'warning')
    return redirect(url_for('inventory'))

# sales tracking logic (objective 1.3.2-III)
@app.route('/sell/<int:id>', methods=['POST'])
@login_required
def sell_product(id):
    product = Product.query.get_or_404(id)
    try:
        qty = int(request.form.get('quantity', 0))
    except ValueError:
        qty = 0

    # check if selling quantity is higher than physical stock
    if qty <= 0:
        flash('Invalid quantity entered.', 'danger')
    elif product.stock_quantity >= qty:
        # calculate financial metrics at time of sale
        revenue = qty * product.selling_price
        cost = qty * product.cost_price
        profit = revenue - cost
        
        # record the sale and update stock
        sale = Sale(product_id=id, quantity=qty, total_revenue=revenue, total_cost=cost, total_profit=profit)
        product.stock_quantity -= qty
        
        db.session.add(sale)
        db.session.commit()
        flash(f'Sale recorded: {qty} {product.name}', 'success')
    else:
        flash(f'Insufficient stock. Only {product.stock_quantity} available.', 'danger')
    
    return redirect(url_for('inventory'))

# stock reconciliation (objective 1.3.2-V and theft detection)
@app.route('/audit', methods=['GET', 'POST'])
@login_required
def audit():
    if request.method == 'POST':
        pid = request.form.get('product_id')
        p_count = int(request.form.get('physical_count', 0))
        product = Product.query.get(pid)
        
        # identify missing items (discrepancy)
        diff = product.stock_quantity - p_count
        audit_entry = StockAudit(
            product_id=pid,
            system_stock=product.stock_quantity,
            physical_count=p_count,
            discrepancy=diff,
            notes=request.form.get('notes')
        )
        # correct system stock to match shelf count
        product.stock_quantity = p_count
        
        db.session.add(audit_entry)
        db.session.commit()
        flash('Audit logged. Stock count corrected.', 'info')
        return redirect(url_for('audit'))
    
    products = Product.query.all()
    audits = StockAudit.query.order_by(StockAudit.audit_date.desc()).all()
    return render_template('audit.html', products=products, audits=audits)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
