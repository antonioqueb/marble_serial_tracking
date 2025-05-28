# models/procurement_group.py
from odoo import models, api, fields
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
            try:
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


class PurchaseStockRule(models.Model):
    _inherit = 'stock.rule'
    _name = 'stock.rule'  # Mantener el mismo nombre del modelo
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Para productos con tracking: SIEMPRE crear nueva línea
        """
        # Usar el método del módulo purchase_stock
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
    
    def _update_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, line):
        """
        Sobrescribir para productos con tracking: NUNCA actualizar línea existente
        """
        if product_id.tracking != 'none':
            _logger.info(f"Producto {product_id.name} con tracking - NO actualizar línea existente, forzar nueva")
            
            # Para productos con tracking, no actualizar la línea existente
            # Esto forzará al sistema a crear una nueva línea
            po = line.order_id
            
            # Preparar valores para nueva línea
            new_line_vals = {
                'product_id': product_id.id,
                'product_qty': product_qty,
                'product_uom': product_uom.id,
                'price_unit': 0.0,  # Se calculará automáticamente
                'name': product_id.name,
                'order_id': po.id,
                'date_planned': fields.Date.today(),
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'bundle_code': values.get('bundle_code', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            }
            
            # Crear nueva línea
            new_line = self.env['purchase.order.line'].create(new_line_vals)
            _logger.info(f"Nueva línea PO creada: ID {new_line.id} para {product_id.name}")
            
            return new_line
            
        # Para productos sin tracking, comportamiento normal
        return super()._update_purchase_order_line(product_id, product_qty, product_uom, company_id, values, line)
    
    def _make_po_get_domain(self, company_id, values, partner):
        """
        Modificar dominio para productos con tracking
        """
        domain = super()._make_po_get_domain(company_id, values, partner)
        
        # Si hay datos de mármol (producto con tracking), forzar nueva PO para cada procurement
        if values.get('marble_height') or values.get('marble_width') or values.get('lot_general'):
            # Agregar el procurement group específico al dominio para asegurar unicidad
            group_id = values.get('group_id')
            if group_id:
                domain.append(('group_id', '=', group_id.id))
                _logger.info(f"Producto con tracking - usando group_id específico: {group_id.name}")
            
        return domain