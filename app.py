import os
import time
import logging
from flask import (
    Flask, render_template, request,
    send_from_directory
)
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.errorhandler(405)
def method_not_allowed(e):
    allowed = e.valid_methods or []
    return (
        f"<h3>405 Method Not Allowed</h3>"
        f"<p>Your request used <strong>{request.method}</strong> "
        f"but this URL only allows: {allowed}</p>"
    ), 405

@app.route('/', methods=['GET'])
def landing():
    return render_template('landing.html')

@app.route('/individual', methods=['GET', 'POST'])
def individual():
    result = None
    error  = None

    if request.method == 'POST':
        try:
            f = request.files['excel_file']
            df = pd.read_excel(f,
                               sheet_name='Active Employees',
                               header=1)

            # — DATA CLEANING —
            df = df[df['Employee ID'].notna()]
            df['Monthly salary applicable for Gratuity calculation'] = pd.to_numeric(
                df['Monthly salary applicable for Gratuity calculation'],
                errors='coerce'
            )
            df = df[df['Monthly salary applicable for Gratuity calculation'].notna()]

            # — FORM INPUTS —
            emp_id         = request.form['emp_id']
            target_y       = int(request.form['target_year'])
            inc_pct        = float(request.form['inc_pct']) / 100
            disc_pct       = float(request.form['disc_pct']) / 100
            retirement_age = int(request.form['retirement_age'])

            # — LOOKUP EMPLOYEE —
            row = df[df['Employee ID'] == emp_id]
            if row.empty:
                raise ValueError(f"No record for Employee ID '{emp_id}'")

            # — EXTRACT DATA —
            S   = float(row['Monthly salary applicable for Gratuity calculation'].iloc[0])
            doj = pd.to_datetime(
                row['Date of Joining (DD/MM/YYYY)'].iloc[0],
                dayfirst=True
            )
            dob = pd.to_datetime(
                row['Date of Birth (DD/MM/YYYY)'].iloc[0],
                dayfirst=True
            )

            current_year = datetime.now().year

            # — COMPUTE EFFECTIVE YEARS —
            retirement_year   = dob.year + retirement_age
            effective_year    = min(target_y, retirement_year)
            m = effective_year - doj.year
            n = effective_year - current_year

            # — APPLY RULES —
            if m < 5:
                gratuity = 0
            else:
                raw = S * (1 + inc_pct)**n * (15/26) * m * (1 - disc_pct)**n
                gratuity = min(raw, 2_000_000)

            result = round(gratuity, 2)

        except Exception as e:
            error = str(e)

    return render_template('individual.html',
                           result=result,
                           error=error)

@app.route('/company', methods=['GET', 'POST'])
def company():
    table_html = None
    total      = None
    download_fn= None

    if request.method == 'POST':
        try:
            f = request.files['excel_file']
            df = pd.read_excel(f,
                               sheet_name='Active Employees',
                               header=1)

            # — DATA CLEANING —
            df = df[df['Employee ID'].notna()]
            df['Monthly salary applicable for Gratuity calculation'] = pd.to_numeric(
                df['Monthly salary applicable for Gratuity calculation'],
                errors='coerce'
            )
            df = df[df['Monthly salary applicable for Gratuity calculation'].notna()]

            # — FORM INPUTS —
            target_y       = int(request.form['target_year'])
            inc_pct        = float(request.form['inc_pct']) / 100
            disc_pct       = float(request.form['disc_pct']) / 100
            retirement_age = int(request.form['retirement_age'])

            # — CALC FUNCTION —
            def calc(row):
                S   = float(row['Monthly salary applicable for Gratuity calculation'])
                doj = pd.to_datetime(
                    row['Date of Joining (DD/MM/YYYY)'],
                    dayfirst=True
                )
                dob = pd.to_datetime(
                    row['Date of Birth (DD/MM/YYYY)'],
                    dayfirst=True
                )
                retirement_year   = dob.year + retirement_age
                effective_year    = min(target_y, retirement_year)
                m = effective_year - doj.year
                n = effective_year - datetime.now().year

                if m < 5:
                    return 0.0
                raw = S * (1 + inc_pct)**n * (15/26) * m * (1 - disc_pct)**n
                return min(raw, 2_000_000)

            df['Gratuity'] = df.apply(calc, axis=1).round(2)
            report = df[['Employee ID', 'Name', 'Gratuity']]

            total = report['Gratuity'].sum().round(2)
            table_html = report.to_html(index=False, classes='report-table')

            # — SAVE FOR DOWNLOAD —
            ts = int(time.time())
            fn = f"gratuity_report_{ts}.xlsx"
            path = os.path.join(UPLOAD_FOLDER, secure_filename(fn))
            report.to_excel(path, index=False)
            download_fn = fn

        except Exception as e:
            table_html = f"<p class='error'>Error: {e}</p>"

    return render_template('company.html',
                           table_html=table_html,
                           total=total,
                           download_fn=download_fn)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    for rule in app.url_map.iter_rules():
        logging.info(f"Route {rule.rule!r} → methods={rule.methods}")
    app.run(debug=True)
