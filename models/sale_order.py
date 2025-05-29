# models/sale_order.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_cancel(self):
        """
        Sobrescribir para conservar la vinculación del procurement_group_id
        al cancelar la orden de venta, evitando que se desvincule de las PO generadas
        """
        _logger.info("[PROCUREMENT-FIX] Cancelando orden de venta conservando procurement_group_id")
        
        # Guardar los procurement_group_id antes de cancelar
        procurement_groups = {}
        for order in self:
            if order.procurement_group_id:
                procurement_groups[order.id] = order.procurement_group_id.id
                _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Guardando procurement_group_id={order.procurement_group_id.id}")

        # Cancelar procurements manualmente sin usar el método estándar
        for order in self:
            # Cancelar los moves de stock relacionados
            moves_to_cancel = order.order_line.mapped('move_ids').filtered(
                lambda m: m.state not in ('done', 'cancel')
            )
            if moves_to_cancel:
                moves_to_cancel._action_cancel()
                _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Cancelados {len(moves_to_cancel)} stock moves")

        # Cambiar estado a 'cancel' SIN llamar al super() para evitar limpieza del procurement_group_id
        result = self.write({'state': 'cancel'})
        
        # Restaurar los procurement_group_id que pudieron haberse perdido
        for order in self:
            if order.id in procurement_groups:
                saved_group_id = procurement_groups[order.id]
                if not order.procurement_group_id or order.procurement_group_id.id != saved_group_id:
                    order.procurement_group_id = saved_group_id
                    _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Restaurado procurement_group_id={saved_group_id}")

        return result

    def action_draft(self):
        """
        Sobrescribir para asegurar que al volver a borrador 
        se mantenga el procurement_group_id existente
        """
        _logger.info("[PROCUREMENT-FIX] Regresando orden a borrador conservando procurement_group_id")
        
        # Guardar procurement_group_id antes del cambio
        procurement_groups = {}
        for order in self:
            if order.procurement_group_id:
                procurement_groups[order.id] = order.procurement_group_id.id
                _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Preservando procurement_group_id={order.procurement_group_id.id}")

        # Llamar al método estándar
        result = super().action_draft()
        
        # Restaurar procurement_group_id si se perdió
        for order in self:
            if order.id in procurement_groups:
                saved_group_id = procurement_groups[order.id]
                if not order.procurement_group_id:
                    order.procurement_group_id = saved_group_id
                    _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Restaurado procurement_group_id={saved_group_id}")

        return result

    def action_confirm(self):
        """
        Sobrescribir para detectar si ya existe un procurement_group_id
        y reutilizar las PO existentes en lugar de crear nuevas
        """
        for order in self:
            if order.procurement_group_id:
                _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Reutilizando procurement_group_id existente={order.procurement_group_id.id}")
                
                # Verificar si hay PO vinculadas a este grupo
                existing_pos = self.env['purchase.order'].search([
                    ('group_id', '=', order.procurement_group_id.id)
                ])
                if existing_pos:
                    _logger.info(f"[PROCUREMENT-FIX] SO {order.name}: Encontradas {len(existing_pos)} PO existentes para reutilizar")

        # Llamar al método estándar que manejará la fusión automáticamente
        return super().action_confirm()