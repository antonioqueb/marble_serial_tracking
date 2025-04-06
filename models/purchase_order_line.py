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
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0
            line.marble_sqm = altura * ancho
            _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: altura={altura}, ancho={ancho} → m²={line.marble_sqm}")

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        for line in self:
            _logger.info(f"[MARBLE-ONCHANGE] (onchange) PO Line ID {line.id} → altura={line.marble_height}, ancho={line.marble_width}, lote={line.lot_general}")

    def write(self, vals):
        for line in self:
            _logger.info(f"[MARBLE-WRITE] Intentando escribir en PO Line {line.id} con: {vals}")
        res = super().write(vals)
        for line in self:
            _logger.info(f"[MARBLE-WRITE] Línea PO {line.id} actualizada correctamente")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for vals, line in zip(vals_list, lines):
            _logger.info(f"[MARBLE-CREATE] Línea PO creada ID {line.id} con: altura={vals.get('marble_height')}, ancho={vals.get('marble_width')}, lote={vals.get('lot_general')}")
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()  # Nos aseguramos de estar en singleton
        _logger.info(f"[MARBLE-MOVE-VALS] Ejecutando _prepare_stock_move_vals en PO Line ID {self.id}")
        _logger.info(f"[MARBLE-MOVE-VALS] Datos actuales: altura={self.marble_height}, ancho={self.marble_width}, m²={self.marble_sqm}, lote={self.lot_general}")
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
        })
        _logger.info(f"[MARBLE-MOVE-VALS] Valores enviados al move: {vals}")
        return vals

    def _create_stock_moves(self, picking):
        res = self.env['stock.move']
        for line in self:
            _logger.info(f"[MARBLE-MOVE-CREATE] Ejecutando _create_stock_moves en PO Line ID {line.id}")
            moves = super(PurchaseOrderLine, line)._create_stock_moves(picking)
            _logger.info(f"[MARBLE-MOVE-CREATE] Total moves creados para PO Line ID {line.id}: {len(moves)}")
            for move in moves:
                _logger.info(f"[MARBLE-MOVE-CREATE] Move ID {move.id} creado para producto: {move.product_id.display_name}")
            res |= moves
        return res
# Funcional