"""Terminal sales reports and dependency-free Office Open XML export."""
import base64
import io
import re
import zipfile
from datetime import datetime
from decimal import Decimal
from xml.sax.saxutils import escape


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def build_report(state, branch_id, start, end, cashier=''):
    if not start.tzinfo or not end.tzinfo or start > end:
        raise ValueError('Укажите корректный период с часовым поясом')
    branch_sales = [s for s in state.get('sales', []) if str(s.get('branchId')) == str(branch_id)]
    key = lambda s: str(s.get('cashierId') or 'name:' + s.get('cashier', ''))
    cashiers = {key(s): s.get('cashier', '—') for s in branch_sales}
    selected = [s for s in branch_sales if not cashier or key(s) == cashier]
    within = lambda value: (date := timestamp(value)) is not None and start <= date <= end
    sold = [s for s in selected if within(s.get('createdAt'))]
    returned = [s for s in selected if s.get('refundedAt') and within(s['refundedAt'])]
    dec = lambda value: Decimal(str(value or 0))
    total = lambda rows, field: float(sum((dec(s.get(field)) for s in rows), Decimal(0)))
    methods = {}
    for method in ('cash', 'card', 'qr'):
        def amount(rows):
            return sum((dec(p.get('amount')) for s in rows for p in (s.get('payments') or [{'method': s.get('paymentMethod'), 'amount': s.get('total')}]) if p.get('method') == method), Decimal(0))
        methods[method] = float(amount(sold) - amount(returned))
    products = {}
    for rows, sign in ((sold, 1), (returned, -1)):
        for sale in rows:
            for item in sale.get('items', []):
                price = dec(item.get('price'))
                group = (str(item.get('id')), item.get('name', '—'), item.get('unit', 'порция'), price)
                row = products.setdefault(group, {'name': group[1], 'unit': group[2], 'price': float(price), 'quantity': Decimal(0), 'total': Decimal(0)})
                qty = dec(item.get('quantity')) * sign
                row['quantity'] += qty
                row['total'] += qty * price
    branch = next((b.get('name') for b in state.get('branches', []) if str(b.get('id')) == str(branch_id)), 'Заведение')
    return {'branch': branch, 'from': start.isoformat(), 'to': end.isoformat(), 'cashier': cashiers.get(cashier, 'Все кассиры'), 'cashiers': [{'id': k, 'name': v} for k, v in sorted(cashiers.items(), key=lambda kv: kv[1])], 'count': len(sold), 'refundCount': len(returned), 'gross': total(sold, 'subtotal'), 'discount': total(sold, 'discountAmount'), 'sales': total(sold, 'total'), 'refunds': total(returned, 'total'), 'net': total(sold, 'total') - total(returned, 'total'), 'payments': methods, 'products': [{**r, 'quantity': float(r['quantity']), 'total': float(r['total'])} for r in sorted(products.values(), key=lambda r: r['name'])], 'currency': next((s.get('currency') for s in sold + returned if s.get('currency')), 'KGS')}


def workbook(report, products=True):
    rows = [['Отчёт по продажам'], ['Заведение', report['branch']], ['С', report['from']], ['По', report['to']], ['Кассир', report['cashier']], ['Валюта', report['currency']], [], ['Чеков', report['count']], ['Возвратов', report['refundCount']], ['Продажи до скидок', report['gross']], ['Скидки', report['discount']], ['Оплачено', report['sales']], ['Возвращено', report['refunds']], ['Выручка с учётом возвратов', report['net']], ['Наличные', report['payments']['cash']], ['Карта', report['payments']['card']], ['QR', report['payments']['qr']]]
    if products:
        rows += [[], ['Продажи по товарам с учётом возвратов, до скидок'], ['Наименование', 'Ед.', 'Количество', 'Цена', 'Сумма']]
        rows += [[r['name'], r['unit'], r['quantity'], r['price'], r['total']] for r in report['products']]
    def cell(value, ref):
        if isinstance(value, (int, float)):
            return f'<c r="{ref}"><v>{value}</v></c>'
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
    sheet = ''.join(f'<row r="{i}">' + ''.join(cell(v, f'{chr(65+j)}{i}') for j, v in enumerate(row)) + '</row>' for i, row in enumerate(rows, 1))
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Продажи" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols><col min="1" max="1" width="48" customWidth="1"/><col min="2" max="5" width="24" customWidth="1"/></cols><sheetData>' + sheet + '</sheetData></worksheet>'}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + content)
    return base64.b64encode(buffer.getvalue()).decode('ascii')
