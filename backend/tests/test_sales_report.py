import base64
import io
import zipfile
from datetime import datetime
from xml.etree import ElementTree as ET
import pytest
from app.sales_report import build_report, workbook


def test_report_period_branch_cashier_refunds_and_excel():
    start = datetime.fromisoformat('2026-09-21T00:00:00+06:00')
    end = datetime.fromisoformat('2026-09-21T23:59:59+06:00')
    sale = {'branchId':'b', 'cashierId':1, 'cashier':'Алия', 'createdAt':'2026-09-21T06:00:00Z', 'subtotal':100, 'discountAmount':10, 'total':90, 'payments':[{'method':'cash','amount':30},{'method':'card','amount':60}], 'items':[{'id':'x','name':'=Тест & кофе','unit':'шт','price':50,'quantity':2}]}
    previous = {**sale, 'createdAt':'2026-09-20T06:00:00Z','refundedAt':'2026-09-21T07:00:00Z'}
    state = {'branches':[{'id':'b','name':'Столовая'}], 'sales':[sale,previous,{**sale,'branchId':'other'}, {**sale,'cashierId':2,'cashier':'Бакыт'}]}
    r = build_report(state,'b',start,end,'1')
    assert (r['count'],r['refundCount'],r['sales'],r['refunds'],r['net']) == (1,1,90,90,0)
    assert r['payments'] == {'cash':0,'card':0,'qr':0}
    assert r['products'][0]['quantity'] == 0
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(workbook(r)))) as z:
        for name in z.namelist(): ET.fromstring(z.read(name))
        sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert not sheet.findall('.//s:f',ns)
        assert sheet.find('.//s:c[@r="B8"]/s:v',ns).text == '1'
    assert build_report(state,'b',start,end)['sales'] == 180
    with pytest.raises(ValueError): build_report(state,'b',end,start)


def test_mixed_payment_and_historical_prices():
    start=datetime.fromisoformat('2026-09-21T00:00:00+00:00'); end=datetime.fromisoformat('2026-09-22T00:00:00+00:00')
    sale={'branchId':'b','createdAt':start.isoformat(),'total':12.3,'subtotal':12.3,'payments':[{'method':'cash','amount':2.1},{'method':'card','amount':10.2}], 'items':[{'id':'a','name':'Чай','price':12.3,'quantity':1}]}
    r=build_report({'sales':[sale]},'b',start,end)
    assert r['payments']=={'cash':2.1,'card':10.2,'qr':0}
    assert r['products'][0]['total']==12.3
