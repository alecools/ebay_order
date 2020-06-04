import sys
import csv
import re
from collections import defaultdict

class OrderProcessor:
  def __init__(self, input_file, cost_lookup):
    self.input_file = input_file
    self.cost_lookup = cost_lookup
    self.orders = self.__get_orders()
    self.user_orders = self.__group_orders_by_user()
    self.txn_orders = self.__lookup_costs(self.__group_orders_by_txn())


  def __get_orders(self):
    with open(self.input_file, mode='r') as infile:  
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

  def __group_orders_by_user(self):
    user_orders = defaultdict(dict)
    title_regex=re.compile(r"\[.*?\]")

    for row in self.orders:
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

  def output_shipping_CSV(self):
    output = self.input_file[:-4] + "_shipping.csv"
    with open(output, mode='w') as outfile:
      fieldnames = ['Post To Name', 'Buyer Address 1', 'Post To Address 2', 'Post To City', 'Post To State', 'Post To Postal Code', 'Item Title', 'Quantity', 'Buyer Note']
      writer = csv.DictWriter(outfile, fieldnames=fieldnames)
      writer.writeheader()
      for shipping in self.user_orders.values():
        data = {k: v for k, v in shipping.items() if k in fieldnames}
        writer.writerow(data)
    return output

  def __group_orders_by_txn(self):
    accounts = defaultdict(dict)
    title_regex=re.compile(r"\[.*?\]")
    price_regex = re.compile(r"\d*\.\d{2}")

    for row in self.orders:
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

  def __lookup_costs(self, txn_orders):
    with open(self.cost_lookup, mode='r') as infile:
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

  def output_accounts_CSV(self):
    output = self.input_file[:-4] + "_accounts.csv"
    with open(output, mode='w') as outfile:
      fieldnames = ['Order Number', 'Buyer Username', 'Buyer Name', 'Item Title', 'Quantity', 'Sold For', 'Cost']
      writer = csv.DictWriter(outfile, fieldnames=fieldnames)
      writer.writeheader()
      for order in self.txn_orders.values():
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