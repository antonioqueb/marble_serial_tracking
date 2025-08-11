# models/purchase_order.py

from odoo import models
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_stock_moves(self, picking):
        """
        Sobrescribir para asegurar que cada línea de PO genere su propio move
        """
        self.ensure_one()
        _logger.info("🏭 DEBUG: PurchaseOrder._prepare_stock_moves para orden %s", self.name)
        _logger.info("🏭 DEBUG: Número de líneas en la orden: %s", len(self.order_line))
        
        res = []

        for line in self.order_line:
            _logger.info("📋 DEBUG: Procesando línea orden %s - Producto: %s", line.id, line.product_id.name)
            
            # Crear un move individual para cada línea
            move_vals = line._prepare_stock_move_vals(
                picking, 
                line.price_unit, 
                line.product_qty, 
                line.product_uom
            )
            
            # Asegurar nombre único y datos de mármol
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0
            marble_sqm = line.marble_sqm

            # Recalcula o ajusta marble_sqm según dimensiones
            if altura > 0 and ancho > 0:
                marble_sqm = altura * ancho
            elif not marble_sqm:
                marble_sqm = 0.0

            move_vals.update({
                'name': f"{self.name} - {line.product_id.name} [Línea {line.id}]",
                'marble_height': altura,
                'marble_width': ancho,
                'marble_sqm': marble_sqm,
                'marble_thickness': line.marble_thickness or 0.0,
                'lot_general': line.lot_general or '',
                'numero_contenedor': line.numero_contenedor or '',
                'purchase_line_id': line.id,
                'origin': f"{self.name} - Línea {line.id}",
            })
            
            _logger.info("📋 DEBUG: Move vals para línea %s: %s", line.id, move_vals)
            res.append(move_vals)

        _logger.info("🏭 DEBUG: Total move_vals preparados: %s", len(res))
        return res

    def button_confirm(self):
        """
        Agregar logs al confirmar la orden
        """
        _logger.info("🔘 DEBUG: button_confirm llamado para orden %s", self.name)
        _logger.info("🔘 DEBUG: Estado actual: %s", self.state)
        
        result = super().button_confirm()
        
        _logger.info("🔘 DEBUG: Orden confirmada. Nuevo estado: %s", self.state)
        
        # Log de los pickings creados
        pickings = self.picking_ids
        _logger.info("🔘 DEBUG: Pickings creados: %s", len(pickings))
        
        for picking in pickings:
            _logger.info("📦 DEBUG: Picking %s - Moves: %s", picking.name, len(picking.move_ids_without_package))
            for move in picking.move_ids_without_package:
                _logger.info("📦 DEBUG: Move %s - Producto: %s, Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.product_id.name, move.marble_height, move.marble_width, 
                           move.marble_sqm, move.lot_general)
        
        return result