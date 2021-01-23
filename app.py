from flask import Flask, render_template, request
from Database.DatabaseClient import DatabaseClient
import datetime
import pandas as pd


app = Flask(__name__)

database_client = DatabaseClient()


@app.template_filter('stock_code_normalizer')
def stock_code_normalizer(code):
    return code[-2:] + code[:-3]


@app.route('/vip/dshj')
def vip_dshj():
    date = datetime.date.today()
    date = date + datetime.timedelta(days=-date.day+1)
    date = date.strftime('%Y-%m-%d')
    return render_template('vip/dshj.html',
                           strategy_cci_date=date,
                           strategy_cci_daily_min=100,
                           strategy_cci_daily_max=300,
                           strategy_cci_weekly_min=150,
                           strategy_cci_weekly_max=300,
                           strategy_cci_monthly_min=200,
                           strategy_cci_monthly_max=400,
                           strategy_cci_all_satisfy='on')


@app.route('/vip/dshj_cci', methods=['GET', 'POST'])
def vip_dshj_cci():

    stocks = {}

    if request.method == 'POST':

        daily_cci_min = request.form.get('strategy_cci_daily_min', None)
        daily_cci_max = request.form.get('strategy_cci_daily_max', None)
        weekly_cci_min = request.form.get('strategy_cci_weekly_min', None)
        weekly_cci_max = request.form.get('strategy_cci_weekly_max', None)
        monthly_cci_min = request.form.get('strategy_cci_monthly_min', None)
        monthly_cci_max = request.form.get('strategy_cci_monthly_max', None)
        all_satisfy = ("on" == request.form.get('strategy_cci_all_satisfy', ""))
        start_date = request.form.get('strategy_cci_date', None)

        audit_event = pd.DataFrame({'date': [pd.datetime.today().strftime("%Y-%m-%d %H:%M:%S")],
                                    'ip': [request.remote_addr],
                                    'event': [str({
                                        'url': '/vip/dshj_cci',
                                        'daily_cci_min': daily_cci_min,
                                        'daily_cci_max': daily_cci_max,
                                        'weekly_cci_min': weekly_cci_min,
                                        'weekly_cci_max': weekly_cci_max,
                                        'monthly_cci_min': monthly_cci_min,
                                        'monthly_cci_max': monthly_cci_max,
                                        'all_satisfy': all_satisfy,
                                        'start_date': start_date
                                    })]})
        database_client.write_audit_event(audit_event)

        if start_date:

            def end_of_week(date):
                return date + datetime.timedelta(days=6-date.weekday())

            def end_of_month(date):
                if date.month in [1, 3, 5, 7, 8, 10, 12]:
                    return datetime.date(date.year, date.month, 31)
                elif date.month in [4, 6, 9, 11]:
                    return datetime.date(date.year, date.month, 30)
                else:
                    return datetime.date(date.year, date.month, 29 if date.year % 4 == 0 else 28)

            def min_max_range(min, max):
                if min and max:
                    return (min, max)
                elif min:
                    return (min, 1000000000)
                elif max:
                    return (-1000000000, max)
                else:
                    return None

            strategies = [
                ('Daily_CCI_14',   daily_cci_min,   daily_cci_max,   end_of_week),
                ('Weekly_CCI_14',  weekly_cci_min,  weekly_cci_max,  end_of_month),
                ('Monthly_CCI_14', monthly_cci_min, monthly_cci_max, None)
            ]

            successful = True
            start_date = pd.to_datetime(start_date).strftime('%Y%m%d')
            stocks_query = pd.DataFrame({'code': [], 'name': [], 'date': []})
            template_sql = "SELECT a.code, b.name, a.date FROM TradeIndicator a, StockBasic b WHERE a.name = '%s' AND a.date >= '%s' AND a.value >= %s AND a.value <= %s AND a.code = b.code"
            for (metric, min, max, date_apply) in strategies:
                range = min_max_range(min, max)
                if range:
                    sql = template_sql % (metric, start_date, range[0], range[1])
                    query = pd.read_sql_query(sql, database_client.get_engine())
                    if query.empty and all_satisfy:
                        successful = False
                        break
                    if not stocks_query.empty and all_satisfy:
                        query.set_index(query.apply(lambda row: "%s_%s" % (row[0], row[2].strftime('%Y%m%d')), axis=1), inplace=True)
                        stocks_query.set_index(stocks_query.apply(lambda row: "%s_%s" % (row[0], row[2].strftime('%Y%m%d')), axis=1), inplace=True)
                        stocks_joint = stocks_query.join(query, how="inner", rsuffix='_r')
                        if stocks_joint.empty:
                            successful = False
                            break
                        stocks_query = stocks_joint[['code', 'name', 'date']]
                    else:
                        stocks_query = stocks_query.append(query)
                    if date_apply:
                        stocks_query['date'] = stocks_query.date.apply(lambda x: date_apply(x))
                        stocks_query = stocks_query.drop_duplicates()

            if successful:
                stocks_query = stocks_query[['code', 'name']]
                stocks_query = stocks_query.drop_duplicates()
                stocks = stocks_query.to_dict(orient='records')

    return render_template('common/stocks.html', stocks=stocks)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)