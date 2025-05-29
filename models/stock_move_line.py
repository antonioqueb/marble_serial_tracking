# models/stock_move_line.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote General')
    bundle_code = fields.Char('Bundle Code')
    marble_thickness = fields.Float('Grosor (cm)')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = (line.marble_height or 0.0) * (line.marble_width or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        lots_env = self.env['stock.lot']
        seq_env = self.env['ir.sequence'].sudo()

        for vals in vals_list:
            _logger.debug("[SML-CREATE|PRE] vals=%s", vals)

        for vals in vals_list:
            if vals.get('lot_id') or not vals.get('lot_general'):
                continue

            bundle_code_val = vals.get('bundle_code')

            picking_code = vals.get('picking_code')
            if not picking_code:
                move = self.env['stock.move'].browse(vals.get('move_id'))
                picking_code = move.picking_type_id.code

            if picking_code != 'incoming':
                continue

            lot_general = vals['lot_general']
            product_id = vals.get('product_id')

            seq_code = f"marble.serial.{lot_general}"
            sequence = seq_env.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = seq_env.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })

            lot_name = sequence.next_by_id()
            vals['lot_id'] = lots_env.create({
                'name': lot_name,
                'product_id': product_id,
                'company_id': vals.get('company_id'),
                'marble_height': vals.get('marble_height'),
                'marble_width': vals.get('marble_width'),
                'marble_sqm': (vals.get('marble_height') or 0.0) * (vals.get('marble_width') or 0.0),
                'lot_general': lot_general,
                'bundle_code': bundle_code_val,
                'marble_thickness': vals.get('marble_thickness', 0.0),
            }).id

        move_lines = super().create(vals_list)
        return move_lines

    def write(self, vals):
        lots_env = self.env['stock.lot']
        seq_env = self.env['ir.sequence'].sudo()

        for line in self:
            if 'lot_general' in vals and vals['lot_general'] and not line.lot_id:
                picking_code = line.picking_id.picking_type_id.code
                if picking_code != 'incoming':
                    continue

                lot_general = vals['lot_general']
                product_id = vals.get('product_id', line.product_id.id)

                seq_code = f"marble.serial.{lot_general}"
                sequence = seq_env.search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    sequence = seq_env.create({
                        'name': _('Secuencia Mármol %s') % lot_general,
                        'code': seq_code,
                        'padding': 3,
                        'prefix': f"{lot_general}-",
                    })

                lot_name = sequence.next_by_id()
                lot_vals = {
                    'name': lot_name,
                    'product_id': product_id,
                    'company_id': line.company_id.id,
                    'marble_height': vals.get('marble_height', line.marble_height),
                    'marble_width': vals.get('marble_width', line.marble_width),
                    'marble_sqm': (vals.get('marble_height', line.marble_height) or 0.0) * (vals.get('marble_width', line.marble_width) or 0.0),
                    'lot_general': lot_general,
                    'bundle_code': vals.get('bundle_code', line.bundle_code),
                    'marble_thickness': vals.get('marble_thickness', line.marble_thickness),
                }
                new_lot = lots_env.create(lot_vals)
                vals['lot_id'] = new_lot.id

        return super().write(vals)
