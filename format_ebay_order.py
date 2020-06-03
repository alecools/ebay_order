from flask import Flask, request, flash, redirect, send_from_directory, url_for, Blueprint
from werkzeug.utils import secure_filename
import sys, os
import csv
import re
from collections import defaultdict

UPLOAD_FOLDER = './orders/'
COST_LOOKUP = UPLOAD_FOLDER + 'cost_lookup.csv'
ALLOWED_EXTENSIONS = {'csv'}

def get_orders(input_file):
  with open(input_file, mode='r') as infile:  
    reader = csv.DictReader(infile)
    # build a list of all orders
    orders = [{
      'Buyer Username': row['Buyer Username'],
      'Post To Name': row['Post To Name'],
      'Buyer Address 1': row['Buyer Address 1'],
      'Post To Address 2': row['Post To Address 2'],
      'Post To City': row['Post To City'],
      'Post To State': row['Post To State'],
      'Post To Postal Code': row['Post To Postal Code'],
      'Item Title': row['Item Title'],
      'Quantity': row['Quantity'],
      'Buyer Note': row['Buyer Note'],
      'Order Number': row['Order Number'],
      'Buyer Name': row['Buyer Name'],
      'Sold For': row['Sold For'],
      'Postage And Handling': row['Postage And Handling']
      } for row in reader]
  return orders

def group_orders_by_user(orders):
  user_orders = defaultdict(dict)
  title_regex=re.compile(r"\[.*?\]")

  for row in orders:
    if row['Buyer Username']:
      if user_orders[row['Buyer Username']]:
        if row['Item Title']:
          # Known user & (single order or line item)
          # No processing required for Known user with new group order as title and qty are handled in line items
          user_orders[row['Buyer Username']]['Item Title'] = user_orders[row['Buyer Username']]['Item Title'] + title_regex.search(row['Item Title']).group() + 'x' + row['Quantity'] + '/'
          user_orders[row['Buyer Username']]['Quantity'] = int(user_orders[row['Buyer Username']]['Quantity']) + int(row['Quantity'])
      else:
        if row['Item Title']:
          # New user & single order
          user_orders[row['Buyer Username']] = {key : value for key, value in row.items() if key not in ['Buyer Username', 'Item Title']}
          user_orders[row['Buyer Username']]['Item Title'] = title_regex.search(row['Item Title']).group() + 'x' + row['Quantity']
        else:
          # New user & group order
          user_orders[row['Buyer Username']] = {key : value for key, value in row.items() if key not in ['Buyer Username', 'Quantity']}
          user_orders[row['Buyer Username']]['Quantity'] = '0'
  return user_orders

def output_shipping_CSV(user_orders, inpunt_file):
  output = inpunt_file[:-4] + "_shipping.csv"
  with open(output, mode='w') as outfile:
    fieldnames = ['Post To Name', 'Buyer Address 1', 'Post To Address 2', 'Post To City', 'Post To State', 'Post To Postal Code', 'Item Title', 'Quantity', 'Buyer Note']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    for shipping in user_orders.values():
      data = {k: v for k, v in shipping.items() if k in fieldnames}
      writer.writerow(data)
  return output

def group_orders_by_txn(orders):
  accounts = defaultdict(dict)
  title_regex=re.compile(r"\[.*?\]")
  price_regex = re.compile(r"\d*\.\d{2}")

  for row in orders:
    if row['Order Number'] and row['Order Number'][0]!="r":
      if accounts[row['Order Number']]:
        if row['Item Title']:
          # Line item
          accounts[row['Order Number']]['Item'].append((title_regex.search(row['Item Title']).group(), row['Quantity']))
      else:
        if row['Item Title']:
          # New single order
          accounts[row['Order Number']] = {key : value for key, value in row.items() if key not in ['Item Title', 'Sold For', 'Postage And Handling']}
          accounts[row['Order Number']]['Item'] = [(title_regex.search(row['Item Title']).group(), row['Quantity'])]
          accounts[row['Order Number']]['Sold For'] = float(price_regex.search(row['Sold For']).group()) * int(row['Quantity'])
          accounts[row['Order Number']]['Postage And Handling'] = float(price_regex.search(row['Postage And Handling']).group())
        else:
          # New group order
          accounts[row['Order Number']] = {key : value for key, value in row.items() if key not in ['Item Title', 'Sold For', 'Postage And Handling']}
          accounts[row['Order Number']]['Item'] = []
          accounts[row['Order Number']]['Sold For'] = float(price_regex.search(row['Sold For']).group())
          accounts[row['Order Number']]['Postage And Handling'] = float(price_regex.search(row['Postage And Handling']).group())

      accounts[row['Order Number']]['Sold For'] = round(accounts[row['Order Number']]['Sold For'], 2)
  return accounts

def lookup_costs(lookup_file, txn_orders):
  with open(lookup_file, mode='r') as infile:
    reader = csv.DictReader(infile)
    cost_lookup = { '[' + row['Item'] + ']': row['Cost'] for row in reader }

  for order in txn_orders.values():
    item_with_cost = []
    for item, qty in order['Item']:
      try:
        item_with_cost.append((item, qty, float(cost_lookup[item]) * int(qty)))
      except:
        item_with_cost.append((item, qty, "NA"))
    
    txn_orders[order['Order Number']]['Item'] = item_with_cost
  return txn_orders

def output_accounts_CSV(txn_orders, inpunt_file):
  output = inpunt_file[:-4] + "_accounts.csv"
  with open(output, mode='w') as outfile:
    fieldnames = ['Order Number', 'Buyer Username', 'Buyer Name', 'Item Title', 'Quantity', 'Sold For', 'Cost']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    for order in txn_orders.values():
      data = {k: v for k, v in order.items() if k in fieldnames and k != 'Item'}
      data['Item Title'] = ""
      data['Cost'] = 0
      for title, qty, cost in order['Item']:
        data['Item Title'] += title + 'x' + qty + '/'
        if cost == "NA" or data['Cost'] == "NA":
          data['Cost'] = "NA"
        else:
          data['Cost'] += float(cost)
      if data['Cost'] != "NA":
        data['Cost'] = round(data['Cost'], 2)
      writer.writerow(data)
  return output

def allowed_file(filename):
  return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_order(input_file):
  orders = get_orders(input_file)
  user_orders = group_orders_by_user(orders)
  shipping_file = output_shipping_CSV(user_orders, input_file)
  txn_orders = lookup_costs(COST_LOOKUP, group_orders_by_txn(orders))
  accounts_file = output_accounts_CSV(txn_orders, input_file)
  return accounts_file, shipping_file
  
def create_app():
  app = Flask(__name__)
  app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
  app.secret_key = "alecools"

  @app.route('/uploads/<filename>')
  def uploaded_file(filename):
      return send_from_directory(app.config['UPLOAD_FOLDER'],
                                filename)

  @app.route('/', methods=['GET', 'POST'])
  def upload_file():
    if request.method == 'POST':
      # check if the post request has the file part
      if 'file' not in request.files:
        return redirect(url_for('error', message="No file component in request payload"))
      file = request.files['file']

      # if user does not select file, browser also
      # submit an empty part without filename
      if file.filename == '':
        return redirect(url_for('error', message="No file selected"))

      if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
      
        # Actual processing of the order file
        accounts_file, shipping_file = format_order(app.config['UPLOAD_FOLDER'] + filename)
        
        return '''
          <!doctype html>
          <title>Order Processed</title>
          <h1>Order Processed</h1>
          <p><a href="/uploads/''' + accounts_file + '''">Accounts File</a></p>
          <p><a href="/uploads/''' + shipping_file + '''">Shipping File</a></p>
          ''' 
      
      else:
        return redirect(url_for('error', message="File type not supported"))

    return '''
      <!doctype html>
      <title>Upload New Order File</title>
      <h1>Upload new File</h1>
      <form method=post enctype=multipart/form-data>
        <input type=file name=file>
        <input type=submit value=Upload>
      </form>
      '''

  @app.route('/error', methods=['GET'])
  def error(message):
    return '''
      <!doctype html>
      <title>Error</title>
      <h1>''' + message + '''</h1>
      '''
  return app