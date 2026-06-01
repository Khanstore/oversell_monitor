from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CreatePoWizardLine(models.TransientModel):
    _name = 'oversell.create.po.wizard.line'
    _description = 'PO Wizard Line'

    wizard_id = fields.Many2one('oversell.create.po.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    deficit_qty = fields.Float(string='Deficit Qty', digits='Product Unit of Measure')
    qty_to_order = fields.Float(string='Qty to Order', digits='Product Unit of Measure')
    last_purchase_price = fields.Float(string='Unit Price', digits='Product Price')

    @api.onchange('deficit_qty')
    def _onchange_deficit_qty(self):
        if self.deficit_qty and not self.qty_to_order:
            self.qty_to_order = self.deficit_qty


class CreatePoWizard(models.TransientModel):
    _name = 'oversell.create.po.wizard'
    _description = 'Create Purchase Order for Oversell Deficit'

    line_ids = fields.One2many(
        'oversell.create.po.wizard.line', 'wizard_id', string='Products')
    note = fields.Text(string='Notes / Instructions')
    scheduled_date = fields.Date(string='Requested Delivery Date')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'line_ids' in fields_list and 'default_line_ids' in self.env.context:
            lines = []
            for l in self.env.context['default_line_ids']:
                vals = l[2] if len(l) == 3 else {}
                vals['qty_to_order'] = vals.get('deficit_qty', 0)
                lines.append((0, 0, vals))
            res['line_ids'] = lines
        return res

    def action_create_po(self):
        if not self.line_ids:
            raise UserError(_('No products to order.'))

        delivery_date = self.scheduled_date or fields.Date.today()

        # Group lines by vendor
        by_vendor = {}
        for line in self.line_ids:
            vid = line.vendor_id.id if line.vendor_id else False
            by_vendor.setdefault(vid, []).append(line)

        po_ids = []
        for vendor_id, lines in by_vendor.items():
            po_line_vals = []
            for l in lines:
                po_line_vals.append((0, 0, {
                    'product_id': l.product_id.id,
                    'product_qty': l.qty_to_order,
                    'price_unit': l.last_purchase_price,
                    'date_planned': delivery_date,
                    'name': l.product_id.display_name or '',
                }))

            po_vals = {
                'partner_id': vendor_id or self.env.company.partner_id.id,
                'date_planned': delivery_date,
                'order_line': po_line_vals,
            }
            po = self.env['purchase.order'].create(po_vals)
            # Add note as internal message if provided
            if self.note:
                po.message_post(body=self.note)
            po_ids.append(po.id)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders Created'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', po_ids)],
        }
