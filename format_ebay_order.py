from flask import Flask, request, flash, redirect, send_from_directory, url_for, Blueprint
from werkzeug.utils import secure_filename

import os

from OrderProcessor import OrderProcessor

UPLOAD_FOLDER = './orders/'
COST_LOOKUP = './cost_lookup.csv'
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
  return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
  
def create_app():
  app = Flask(__name__)
  app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
  app.secret_key = "alecools"

  @app.route('/orders/<filename>')
  def download_file(filename):
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
        order_processor = OrderProcessor(app.config['UPLOAD_FOLDER'] + filename, COST_LOOKUP)
        shipping_file = order_processor.output_shipping_CSV()
        accounts_file = order_processor.output_accounts_CSV()
        
        return '''
          <!doctype html>
          <title>Order Processed</title>
          <h1>Order Processed</h1>
          <p><a href="/''' + accounts_file + '''">Accounts File</a></p>
          <p><a href="/''' + shipping_file + '''">Shipping File</a></p>
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