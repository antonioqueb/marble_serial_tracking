from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.picking_code == 'incoming' and line.lot_general:
                sequence_code = 'marble.serial.%s' % line.lot_general
                sequence = self.env['ir.sequence'].sudo().search([('code', '=', sequence_code)], limit=1)
                if not sequence:
                    sequence = self.env['ir.sequence'].sudo().create({
                        'name': 'Secuencia Mármol %s' % line.lot_general,
                        'code': sequence_code,
                        'padding': 3,
                        'prefix': line.lot_general + '-',
                    })
                lot_name = sequence.next_by_id()

                # Crear el número de serie (lot) con valores
                lot = self.env['stock.lot'].create({
                    'name': lot_name,
                    'product_id': line.product_id.id,
                    'company_id': line.company_id.id,
                    'marble_height': line.marble_height,
                    'marble_width': line.marble_width,
                    'marble_sqm': line.marble_sqm,
                    'lot_general': line.lot_general,
                })
                line.lot_id = lot.id
                line.lot_name = lot_name
        return lines
