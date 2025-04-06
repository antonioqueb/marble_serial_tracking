from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('Metros Cuadrados', compute='_compute_marble_sqm', store=True)
    lot_general = fields.Char('Lote General', store=True)

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = line.marble_height * line.marble_width

    def _create_stock_moves(self, picking):
        self.ensure_one()
        moves = super()._create_stock_moves(picking)

        _logger.info("=== INICIO _create_stock_moves ===")
        _logger.info(f"[MARBLE] PO Line ID: {self.id}, estado actual en memoria:")
        _logger.info(f"[MARBLE] marble_height={self.marble_height} ({type(self.marble_height)}), "
                     f"marble_width={self.marble_width} ({type(self.marble_width)}), "
                     f"marble_sqm={self.marble_sqm} ({type(self.marble_sqm)}), "
                     f"lot_general={self.lot_general} ({type(self.lot_general)})")

        # Forzamos lectura de BD para obtener datos reales persistidos
        line = self.browse(self.id).sudo()
        read_data = line.read(['marble_height', 'marble_width', 'marble_sqm', 'lot_general'])[0]

        _logger.info(f"[MARBLE] Datos leídos desde BD para PO Line {self.id}: {read_data}")

        for move in moves:
            move.write({
                'marble_height': read_data.get('marble_height') or 0.0,
                'marble_width': read_data.get('marble_width') or 0.0,
                'marble_sqm': read_data.get('marble_sqm') or 0.0,
                'lot_general': read_data.get('lot_general') or '',
            })
            _logger.info(f"[MARBLE] → stock.move id={move.id} actualizado con: "
                         f"height={read_data.get('marble_height')}, "
                         f"width={read_data.get('marble_width')}, "
                         f"sqm={read_data.get('marble_sqm')}, "
                         f"lote={read_data.get('lot_general')}")

        _logger.info("=== FIN _create_stock_moves ===")
        return moves
