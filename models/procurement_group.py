# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Asegurar que el campo marble_sqm se propague a las líneas de PO
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Propagar el campo marble_sqm si existe en values
        if 'marble_sqm' in values:
            res['marble_sqm'] = values.get('marble_sqm', 0.0)
            _logger.info(f"[MARBLE-PROPAGATE] Propagando m² a PO line para {product_id.name}: marble_sqm={values.get('marble_sqm')}")
            
        # Opcional: si también quieres propagar otros campos en el futuro, agrégalos aquí
        # res['marble_height'] = values.get('marble_height', 0.0)
        # res['marble_width'] = values.get('marble_width', 0.0)
        # res['lot_general'] = values.get('lot_general', '')
        # res['marble_thickness'] = values.get('marble_thickness', 0.0)
        
        return res