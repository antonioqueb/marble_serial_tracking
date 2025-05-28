# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _get_procurements_to_merge(self, procurements):
        """
        Para productos con tracking: NO AGRUPAR NUNCA
        Cada procurement debe generar su propia línea de PO
        """
        merged_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            # Obtener product_id de manera segura desde el procurement
            try:
                # En Odoo 18, procurement es un namedtuple con: (product_id, product_qty, product_uom, location_id, name, origin, company_id, values)
                product_id = procurement.product_id
                
                if product_id.tracking != 'none':
                    # Cada producto con tracking va en su propio grupo (no se agrupa)
                    merged_procurements.append([procurement])
                    _logger.info(f"Producto {product_id.name} con tracking - procesamiento individual")
                else:
                    # Para productos sin tracking, agregar a lista normal
                    normal_procurements.append(procurement)
                    
            except Exception as e:
                _logger.warning(f"Error procesando procurement en merge: {e}, agregando a normal_procurements")
                normal_procurements.append(procurement)
        
        # Procesar productos sin tracking con comportamiento normal
        if normal_procurements:
            try:
                normal_merged = super()._get_procurements_to_merge(normal_procurements)
                merged_procurements.extend(normal_merged)
            except Exception as e:
                _logger.error(f"Error en super()._get_procurements_to_merge: {e}")
                # Fallback: agregar cada procurement normal individualmente
                for proc in normal_procurements:
                    merged_procurements.append([proc])
            
        return merged_procurements
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Para productos con tracking: SIEMPRE crear nueva línea
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        if product_id.tracking != 'none':
            # FORZAR que sea una nueva línea - eliminar cualquier referencia existente
            res.pop('purchase_line_id', None)
            
            # Forzar cantidad exacta (no permitir agrupamiento de cantidades)
            res['product_qty'] = product_qty
            res['product_uom_qty'] = product_qty
            
            # Propagar campos de mármol
            res.update({
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'bundle_code': values.get('bundle_code', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            })
            
            _logger.info(f"Nueva línea PO forzada: {product_id.name} - Qty: {product_qty} - Mármol: {values.get('marble_height')}x{values.get('marble_width')}")
            
        return res
    
    def _make_po_get_domain(self, company_id, values, partner):
        """
        Sobrescribir para crear PO separadas para productos con tracking si es necesario
        """
        domain = super()._make_po_get_domain(company_id, values, partner)
        
        # Si hay datos de mármol (producto con tracking), modificar el dominio para evitar reutilización
        if values.get('marble_height') or values.get('marble_width') or values.get('lot_general'):
            # Agregar condición imposible para forzar nueva PO
            domain.append(('id', '=', -1))  # ID que nunca existirá
            _logger.info("Procurement con datos de mármol - forzando nueva PO")
            
        return domain
    
    def _update_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, line):
        """
        Sobrescribir para productos con tracking: CREAR nueva línea en lugar de actualizar
        """
        if product_id.tracking != 'none':
            _logger.info(f"Producto {product_id.name} con tracking - CREANDO nueva línea en lugar de actualizar existente")
            
            # Crear nueva línea en lugar de actualizar la existente
            po = line.order_id
            new_line_vals = self._prepare_purchase_order_line(
                product_id, product_qty, product_uom, company_id, values, po
            )
            
            # Crear la nueva línea
            new_line = self.env['purchase.order.line'].create(new_line_vals)
            _logger.info(f"Nueva línea PO creada: ID {new_line.id} para {product_id.name}")
            
            return new_line
            
        # Para productos sin tracking, comportamiento normal
        return super()._update_purchase_order_line(product_id, product_qty, product_uom, company_id, values, line)
    
    def _get_purchase_order_line(self, procurements):
        """
        Sobrescribir para forzar creación de nuevas líneas para productos con tracking
        """
        # Procesar cada procurement individualmente para productos con tracking
        lines = self.env['purchase.order.line']
        
        for procurement in procurements:
            product_id = procurement.product_id
            
            if product_id.tracking != 'none':
                _logger.info(f"Producto {product_id.name} con tracking - creando nueva línea sin buscar existente")
                # Para productos con tracking, no buscar líneas existentes, ir directo a crear nueva
                continue  # Esto permitirá que el flujo normal cree una nueva línea
            else:
                # Para productos sin tracking, usar comportamiento normal
                if hasattr(super(), '_get_purchase_order_line'):
                    line = super()._get_purchase_order_line([procurement])
                    lines |= line
        
        return lines
    
    def _check_existing_po_line(self, po, procurement):
        """
        Método personalizado para verificar líneas existentes
        """
        product_id = procurement.product_id
        
        if product_id.tracking != 'none':
            _logger.info(f"Producto {product_id.name} con tracking - NO buscar línea existente")
            return False
            
        # Para productos sin tracking, buscar líneas existentes normalmente
        return po.order_line.filtered(
            lambda line: line.product_id == product_id and 
            line.product_uom == procurement.product_uom
        )