# models/stock_move.py
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    # tracking
    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id    = fields.Many2one('stock.lot', string='Número de Serie (Venta)')

    # mármol + pedimento
    marble_height    = fields.Float('Altura (m)')
    marble_width     = fields.Float('Ancho (m)')
    marble_sqm       = fields.Float('Metros Cuadrados')
    lot_general      = fields.Char ('Lote General')
    pedimento_number = fields.Char ('Número de Pedimento', size=18)

    # ─── utilidades existentes ───
    is_outgoing = fields.Boolean(
        compute='_compute_is_outgoing',
        store=True, string='Es Salida'
    )

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = move.picking_type_id.code == 'outgoing'

    # ─── crear move-line con todos los campos ───
    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        vals.update({
            'lot_id':           self.lot_id.id,
            'marble_height':    self.marble_height,
            'marble_width':     self.marble_width,
            'marble_sqm':       self.marble_sqm,
            'lot_general':      self.lot_general,
            'pedimento_number': self.pedimento_number,
        })
        return vals

    # ─── completar líneas existentes ───
    def _create_move_lines(self):
        res = super()._create_move_lines()
        for move in self:
            for line in move.move_line_ids.filtered(lambda l: not l.pedimento_number):
                line.update({
                    'lot_id':           move.lot_id,
                    'marble_height':    move.marble_height,
                    'marble_width':     move.marble_width,
                    'marble_sqm':       move.marble_sqm,
                    'lot_general':      move.lot_general,
                    'pedimento_number': move.pedimento_number,
                })
        return res
