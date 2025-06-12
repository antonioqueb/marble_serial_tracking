# models/stock_move_line.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = (line.marble_height or 0.0) * (line.marble_width or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        Lot = self.env['stock.lot']
        Seq = self.env['ir.sequence'].sudo()

        for vals in vals_list:
            # Solo para entradas sin lot_id pero con lot_general definido
            if vals.get('lot_general') and not vals.get('lot_id'):
                picking_code = vals.get('picking_code')
                if not picking_code and vals.get('move_id'):
                    move = self.env['stock.move'].browse(vals['move_id'])
                    picking_code = move.picking_type_id.code
                if picking_code == 'incoming':
                    lot_general = vals['lot_general']
                    seq_code = f"marble.serial.{lot_general}"
                    sequence = Seq.search([('code', '=', seq_code)], limit=1)
                    if not sequence:
                        sequence = Seq.create({
                            'name': _('Secuencia Mármol %s') % lot_general,
                            'code': seq_code,
                            'padding': 3,
                            'prefix': f"{lot_general}-",
                        })
                    lot_name = sequence.next_by_id()
                    new_lot = Lot.create({
                        'name': lot_name,
                        'product_id': vals.get('product_id'),
                        'company_id': vals.get('company_id'),
                        'marble_height': vals.get('marble_height'),
                        'marble_width': vals.get('marble_width'),
                        'marble_sqm': (vals.get('marble_height') or 0.0) * (vals.get('marble_width') or 0.0),
                        'lot_general': lot_general,
                        'marble_thickness': vals.get('marble_thickness', 0.0),
                    })
                    vals['lot_id'] = new_lot.id

        return super().create(vals_list)

    def write(self, vals):
        if 'lot_general' not in vals or not vals['lot_general']:
            return super().write(vals)

        Lot = self.env['stock.lot']
        Seq = self.env['ir.sequence'].sudo()
        to_process = self.filtered(lambda l: not l.lot_id and l.picking_id.picking_type_id.code == 'incoming')

        for line in to_process:
            lot_general = vals['lot_general']
            seq_code = f"marble.serial.{lot_general}"
            sequence = Seq.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = Seq.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
            lot_name = sequence.next_by_id()
            new_lot = Lot.create({
                'name': lot_name,
                'product_id': vals.get('product_id', line.product_id.id),
                'company_id': line.company_id.id,
                'marble_height': vals.get('marble_height', line.marble_height),
                'marble_width': vals.get('marble_width', line.marble_width),
                'marble_sqm': (vals.get('marble_height', line.marble_height) or 0.0) * (vals.get('marble_width', line.marble_width) or 0.0),
                'lot_general': lot_general,
                'marble_thickness': vals.get('marble_thickness', line.marble_thickness),
            })
            update_vals = vals.copy()
            update_vals['lot_id'] = new_lot.id
            super(StockMoveLine, line).write(update_vals)

        with_lot = self.filtered(lambda l: l.lot_id)
        if with_lot:
            super(StockMoveLine, with_lot).write(vals)

        return True

    @api.onchange('lot_general')
    def _onchange_lot_general(self):
        if self.lot_general and not self.lot_id:
            return {
                'warning': {
                    'title': _('Información'),
                    'message': _('Al guardar, se generará un número de serie automático.')
                }
            }
