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
                line.lot_name = sequence.next_by_id()
        return lines
