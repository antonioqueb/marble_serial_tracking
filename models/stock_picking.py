# models/stock_picking.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """
        Sobrescribir button_validate para asegurar propagación de datos 
        de mármol antes de validar el picking
        """
        # Validación especial para pickings de salida
        if self.picking_type_id.code == 'outgoing':
            for move in self.move_ids_without_package:
                if move.sale_line_id:
                    # Verificar que los datos de la línea de venta estén en el move
                    sale_line = move.sale_line_id
                    if sale_line.marble_sqm > 0:
                        _logger.info(f"[PICKING-VALIDATE] Verificando move {move.id} contra línea de venta {sale_line.id}")
                        
                        # Actualizar el move con los datos más recientes
                        move.write({
                            'marble_height': sale_line.marble_height,
                            'marble_width': sale_line.marble_width,
                            'marble_sqm': sale_line.marble_sqm,
                            'lot_general': sale_line.lot_general,
                            'marble_thickness': sale_line.marble_thickness,
                            'pedimento_number': sale_line.pedimento_number,
                        })
        
        # Propagar datos de moves a move_lines antes de validar
        for move in self.move_ids_without_package:
            if move.marble_height or move.marble_width or move.lot_general or move.lot_id:
                _logger.info(f"[PICKING-VALIDATE] Propagando datos del move {move.id} antes de validación")
                move._propagate_marble_data_to_move_lines()
        
        # Llamar al método padre
        return super().button_validate()

    def _action_done(self):
        """
        Sobrescribir _action_done para última verificación de datos
        """
        # Última propagación antes de marcar como hecho
        for move in self.move_ids_without_package:
            if move.move_line_ids and (move.marble_height or move.marble_width or move.lot_general):
                move._propagate_marble_data_to_move_lines()
                _logger.info(f"[PICKING-DONE] Datos finales propagados para move {move.id}")
        
        return super()._action_done()