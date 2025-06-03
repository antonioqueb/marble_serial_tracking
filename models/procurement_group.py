# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Asegurar que los campos de mármol se propaguen a las líneas de PO
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Propagar campos de mármol para productos con tracking
        if product_id.tracking != 'none':
            res.update({
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            })
            
            _logger.info(f"Propagando campos de mármol a PO line para {product_id.name}: altura={values.get('marble_height')}, ancho={values.get('marble_width')}, lote={values.get('lot_general')}")
            
        return res