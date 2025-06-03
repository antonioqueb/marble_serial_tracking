# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'
    
    def run(self, procurements, raise_user_error=True):
        """
        Sobrescribir para separar procurements de productos con tracking
        """
        # Separar procurements por tipo de tracking
        tracking_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            # procurement es una tupla (product, qty, uom, location, name, origin, company, values)
            product = procurement[0]
            if product.tracking != 'none':
                tracking_procurements.append(procurement)
                _logger.info(f"[PROCUREMENT-RUN] Producto con tracking {product.name}: procesamiento individual")
            else:
                normal_procurements.append(procurement)
        
        # Procesar productos con tracking individualmente
        for procurement in tracking_procurements:
            super(ProcurementGroup, self).run([procurement], raise_user_error=raise_user_error)
        
        # Procesar productos sin tracking normalmente (agrupados)
        if normal_procurements:
            super(ProcurementGroup, self).run(normal_procurements, raise_user_error=raise_user_error)
        
        return True

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _merge_procurements(self, procurements_to_merge):
        """
        Sobrescribir para evitar el merge de productos con tracking
        """
        # Filtrar solo procurements de productos sin tracking
        procurements_without_tracking = []
        
        for procurement in procurements_to_merge:
            # procurement es una tupla (product, qty, uom, location, name, origin, company, values)
            product = procurement[0]
            if product.tracking == 'none':
                procurements_without_tracking.append(procurement)
                _logger.info(f"[PROCUREMENT-MERGE] Producto sin tracking {product.name}: permitiendo merge")
            else:
                _logger.info(f"[PROCUREMENT-MERGE] Producto con tracking {product.name}: evitando merge")
        
        # Solo hacer merge de productos sin tracking
        if procurements_without_tracking:
            return super()._merge_procurements(procurements_without_tracking)
        else:
            # Si todos los productos tienen tracking, devolver lista vacía
            return []
    
    def _run_buy(self, procurements):
        """
        Sobrescribir para manejar productos con tracking de forma individual
        """
        # Separar procurements por tipo
        tracking_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            # procurement es una tupla (product, qty, uom, location, name, origin, company, values)
            product = procurement[0]
            if product.tracking != 'none':
                tracking_procurements.append(procurement)
            else:
                normal_procurements.append(procurement)
        
        # Procesar productos con tracking individualmente (sin merge)
        for procurement in tracking_procurements:
            _logger.info(f"[RUN-BUY] Procesando individualmente producto con tracking: {procurement[0].name}")
            # Crear una lista con un solo procurement para evitar el merge
            super(StockRule, self)._run_buy([procurement])
        
        # Procesar productos sin tracking normalmente (con merge)
        if normal_procurements:
            _logger.info(f"[RUN-BUY] Procesando {len(normal_procurements)} productos sin tracking con merge normal")
            super(StockRule, self)._run_buy(normal_procurements)
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Modificar para que no busque líneas existentes para productos con tracking
        Y PROPAGAR CORRECTAMENTE todos los campos de mármol
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Logging para debug
        _logger.info(f"[PROCUREMENT-DEBUG] Values recibidos: {values}")
        _logger.info(f"[PROCUREMENT-DEBUG] Producto: {product_id.name}, Tracking: {product_id.tracking}")
        
        # Si el producto tiene tracking, forzar creación de nueva línea
        if product_id.tracking != 'none':
            # Eliminar el ID de línea existente para forzar creación de nueva
            if 'purchase_line_id' in res:
                del res['purchase_line_id']
                
            # ASEGURAR que los campos de mármol se propaguen SIEMPRE
            marble_fields = {
                'order_id': po.id,
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            }
            
            res.update(marble_fields)
            
            _logger.info(f"[PROCUREMENT-DEBUG] Campos de mármol propagados: {marble_fields}")
            _logger.info(f"Creando nueva línea PO para producto con tracking: {product_id.name}")
        else:
            # Para productos sin tracking, también propagar si existen los valores
            marble_fields = {}
            for field in ['marble_height', 'marble_width', 'marble_sqm', 'lot_general', 'marble_thickness']:
                if field in values:
                    marble_fields[field] = values[field]
            
            if marble_fields:
                res.update(marble_fields)
                _logger.info(f"[PROCUREMENT-DEBUG] Campos de mármol propagados (sin tracking): {marble_fields}")
            
        return res