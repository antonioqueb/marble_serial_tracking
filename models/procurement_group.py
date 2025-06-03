# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _run_buy(self, procurements):
        """
        Sobrescribir para asegurar que marble_sqm se propague correctamente
        """
        # Primero, llamar al método padre
        res = super()._run_buy(procurements)
        
        # Después de que se hayan creado/actualizado las líneas de PO,
        # asegurarnos de que marble_sqm se propague
        for procurement in procurements:
            # procurement es una tupla (product, qty, uom, location, name, origin, company, values)
            values = procurement[7] if len(procurement) > 7 else {}
            
            if 'marble_sqm' in values and values.get('marble_sqm', 0.0) > 0:
                # Buscar la línea de PO que se acaba de crear/actualizar
                # mediante el move_dest_ids que se acaba de vincular
                if 'move_dest_ids' in values:
                    move_dest = values.get('move_dest_ids')
                    if move_dest:
                        # Buscar líneas de PO vinculadas a este movimiento
                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', move_dest.ids if hasattr(move_dest, 'ids') else [move_dest.id])
                        ])
                        
                        for po_line in po_lines:
                            if po_line.marble_sqm != values['marble_sqm']:
                                po_line.write({'marble_sqm': values['marble_sqm']})
                                _logger.info(f"[MARBLE-FIX] Actualizada PO line {po_line.id} con marble_sqm={values['marble_sqm']}")
        
        return res
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Asegurar que el campo marble_sqm se propague a las líneas de PO nuevas
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Propagar el campo marble_sqm si existe en values
        if 'marble_sqm' in values:
            res['marble_sqm'] = values.get('marble_sqm', 0.0)
            _logger.info(f"[MARBLE-PROPAGATE] Propagando m² a PO line para {product_id.name}: marble_sqm={values.get('marble_sqm')}")
            
        return res