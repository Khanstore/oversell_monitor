from collections import defaultdict
from markupsafe import escape

from odoo import models, fields, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Capture stock before confirmation and persist genuine order-time shortages.

        This is an event snapshot, separate from the live report. It records a
        single history row per confirmed order/product where this order's total
        demand exceeds the warehouse's free quantity before confirmation.
        """
        snapshots = {}
        for order in self:
            warehouse = order.warehouse_id
            if not warehouse:
                continue
            company = order.company_id
            by_product = defaultdict(lambda: {'qty': 0.0, 'lines': []})
            for line in order.order_line.filtered(lambda l: l.product_id and not l.display_type):
                product = line.product_id.with_company(company)
                if product.type == 'service':
                    continue
                qty = line.product_uom._compute_quantity(line.product_uom_qty, product.uom_id)
                by_product[product.id]['qty'] += qty
                by_product[product.id]['lines'].append(line)

            for product_id, data in by_product.items():
                product = self.env['product.product'].browse(product_id).with_company(company)
                scoped_product = product.with_context(warehouse=warehouse.id)
                snapshots[(order.id, product_id)] = {
                    'order': order,
                    'product': product,
                    'warehouse': warehouse,
                    'company': company,
                    'stock': scoped_product.free_qty,
                    'qty': data['qty'],
                    'lines': data['lines'],
                }

        result = super().action_confirm()
        History = self.env['oversell.history'].sudo()
        for snapshot in snapshots.values():
            deficit = max(snapshot['qty'] - snapshot['stock'], 0.0)
            if deficit <= 0:
                continue
            order = snapshot['order']
            product = snapshot['product']
            if History.search([
                ('order_id', '=', order.id),
                ('product_id', '=', product.id),
            ], limit=1):
                continue
            supplier = product.product_tmpl_id.seller_ids.filtered(
                lambda seller: not seller.company_id or seller.company_id == snapshot['company']
            ).sorted(lambda seller: (seller.sequence, seller.id))[:1]
            vendor = supplier.partner_id if supplier else False
            last_supplier_price = 0.0
            if supplier:
                last_supplier_price = supplier.currency_id._convert(
                    supplier.price, snapshot['company'].currency_id,
                    snapshot['company'], fields.Date.today()
                ) if supplier.currency_id else supplier.price

            history = History.create({
                'event_date': fields.Datetime.now(),
                'order_id': order.id,
                'order_name': order.name,
                'product_id': product.id,
                'vendor_id': vendor.id if vendor else False,
                'vendor_area': (vendor.city or vendor.state_id.name or '') if vendor else '',
                'ordered_qty': snapshot['qty'],
                'stock_at_order': snapshot['stock'],
                'deficit_qty': deficit,
                'avg_cost': product.standard_price,
                'last_purchase_price': last_supplier_price,
                'currency_id': snapshot['company'].currency_id.id,
                'company_id': snapshot['company'].id,
                'notes': _('Captured automatically when the sales order was confirmed.'),
            })

            # Queue optional alerts instead of sending synchronously during order
            # confirmation; mail-server failures must not block a sales order.
            params = self.env['ir.config_parameter'].sudo()
            send_vendor = params.get_param('oversell_monitor.auto_notify_vendor') == 'True'
            send_customer = params.get_param('oversell_monitor.auto_notify_customer') == 'True'
            company_name = escape(snapshot['company'].name or '')
            product_name = escape(product.display_name or '')
            order_name = escape(order.name or '')
            mail_values = []
            if send_vendor and vendor and vendor.email:
                mail_values.append({
                    'subject': _('Restock request: %s') % product.display_name,
                    'body_html': (
                        '<p>Dear %s,</p><p>We have confirmed order %s and need '
                        '<strong>%s</strong>. The estimated shortage is '
                        '<strong>%s</strong> units. Please confirm the earliest '
                        'delivery date.</p><p>Regards,<br/>%s</p>'
                    ) % (escape(vendor.name or ''), order_name, product_name,
                         escape(str(deficit)), company_name),
                    'email_to': vendor.email,
                    'email_from': snapshot['company'].email or self.env.user.email or False,
                    'model': 'oversell.history',
                    'res_id': history.id,
                })
            customer = order.partner_id
            if send_customer and customer and customer.email:
                mail_values.append({
                    'subject': _('Stock delay notice for %s') % order.name,
                    'body_html': (
                        '<p>Dear %s,</p><p>Regarding order <strong>%s</strong>, '
                        '<strong>%s</strong> is currently short by approximately '
                        '<strong>%s</strong> units. We are working on replenishment '
                        'and will update you when we have a delivery estimate.</p>'
                        '<p>Regards,<br/>%s</p>'
                    ) % (escape(customer.name or ''), order_name, product_name,
                         escape(str(deficit)), company_name),
                    'email_to': customer.email,
                    'email_from': snapshot['company'].email or self.env.user.email or False,
                    'model': 'oversell.history',
                    'res_id': history.id,
                })
            if mail_values:
                self.env['mail.mail'].sudo().create(mail_values)
                history.alert_sent = True
        return result
