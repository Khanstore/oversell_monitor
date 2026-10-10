from odoo import models, fields, api, _
from markupsafe import escape


class SendAlertWizardLine(models.TransientModel):
    _name = 'oversell.send.alert.wizard.line'
    _description = 'Alert Wizard Line'

    wizard_id = fields.Many2one('oversell.send.alert.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product')
    vendor_id = fields.Many2one('res.partner', string='Vendor / Recipient')
    order_id = fields.Many2one('sale.order', string='Sale Order')
    deficit_qty = fields.Float(string='Deficit Qty')


class SendAlertWizard(models.TransientModel):
    _name = 'oversell.send.alert.wizard'
    _description = 'Send Oversell Alert'

    alert_type = fields.Selection([
        ('vendor', 'Vendor — restock request'),
        ('customer', 'Customer — delay notice'),
        ('both', 'Both vendor and customer'),
    ], string='Alert Type', default='vendor', required=True)

    line_ids = fields.One2many(
        'oversell.send.alert.wizard.line', 'wizard_id', string='Lines')
    message_body = fields.Html(string='Message', sanitize=True)
    subject = fields.Char(
        string='Subject', default='Stock Alert — Action Required')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'line_ids' in fields_list and 'default_line_ids' in self.env.context:
            lines = [(0, 0, l[2]) for l in self.env.context.get('default_line_ids', [])]
            res['line_ids'] = lines
        return res

    def _build_vendor_body(self, line):
        product_name = escape(line.product_id.display_name or '')
        vendor_name = escape(line.vendor_id.name or 'Supplier')
        company_name = escape(self.env.company.name or '')
        deficit = line.deficit_qty
        return (
            f'<p>Dear {vendor_name},</p>'
            f'<p>We require restocking of <strong>{product_name}</strong> '
            f'(estimated shortage: <strong>{deficit}</strong> units). '
            f'Please confirm your earliest delivery date.</p>'
            f'<p>A formal Purchase Order will be sent separately.</p>'
            f'<p>Best regards,<br/>{company_name}</p>'
        )

    def _build_customer_body(self, line):
        customer_name = escape(line.order_id.partner_id.name if line.order_id else 'Customer')
        product_name = escape(line.product_id.display_name or '')
        order_name = escape(line.order_id.name if line.order_id else '')
        company_name = escape(self.env.company.name or '')
        return (
            f'<p>Dear {customer_name},</p>'
            f'<p>We are writing regarding your order <strong>{order_name}</strong>. '
            f'Unfortunately, <strong>{product_name}</strong> is currently out of stock. '
            f'We are working to fulfil your order as quickly as possible and will '
            f'keep you updated on the expected delivery date.</p>'
            f'<p>We apologise for any inconvenience.</p>'
            f'<p>Best regards,<br/>{company_name}</p>'
        )

    def action_send(self):
        MailMail = self.env['mail.mail'].sudo()
        for line in self.line_ids:
            if self.alert_type in ('vendor', 'both') and line.vendor_id and line.vendor_id.email:
                MailMail.create({
                    'subject': self.subject,
                    'body_html': self.message_body or self._build_vendor_body(line),
                    'email_to': line.vendor_id.email,
                    'email_from': self.env.user.email or self.env.company.email or False,
                }).send()

            if self.alert_type in ('customer', 'both') and line.order_id:
                customer = line.order_id.partner_id
                if customer and customer.email:
                    MailMail.create({
                        'subject': self.subject,
                        'body_html': self.message_body or self._build_customer_body(line),
                        'email_to': customer.email,
                        'email_from': self.env.user.email or self.env.company.email or False,
                    }).send()

        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def action_send_digest(self):
        """Called by cron — sends digest email to managers."""
        config = self.env['ir.config_parameter'].sudo()
        if not config.get_param('oversell_monitor.digest_enabled'):
            return

        lines = self.env['oversell.monitor.line'].search([], limit=500)
        if not lines:
            return

        # Build summary table
        rows = ''.join(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                escape(l.vendor_name or ''), escape(l.product_name or ''),
                escape(str(l.ordered_qty)), escape(str(l.qty_on_hand)),
                escape(str(l.deficit_qty)), escape(str(l.order_date or ''))
            )
            for l in lines
        )
        body = f'''
            <p>Oversell &amp; Out-of-Stock Digest — {len(lines)} open line(s)</p>
            <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">
                <tr><th>Vendor</th><th>Product</th><th>Ordered</th>
                    <th>In Stock</th><th>Deficit</th><th>Order Date</th></tr>
                {rows}
            </table>
            <p>Please log in to Odoo → Oversell Monitor to take action.</p>
        '''

        # Send to all stock managers
        managers = self.env.ref('stock.group_stock_manager').users
        for user in managers:
            if user.email:
                self.env['mail.mail'].sudo().create({
                    'subject': f'Oversell Digest — {len(lines)} lines need attention',
                    'body_html': body,
                    'email_to': user.email,
                    'email_from': self.env.company.email or self.env.user.email or False,
                }).send()
