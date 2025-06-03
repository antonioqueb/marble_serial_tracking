# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model): # Aunque el archivo se llame procurement_group.py, la clase hereda stock.rule
    _inherit = 'stock.rule'

    def _run_buy(self, procurements): # procurements es una lista de tuplas (procurement_request, rule)
        _logger.info(f"[MARBLE-PROCUREMENT] Ejecutando _run_buy para {len(procurements)} procurements")
        procurement_data_to_apply = {}

        # BUCLE 1: Extraer y almacenar los datos de mármol de los procurements
        for procurement_request, rule in procurements: # Iteración corregida
            # procurement_request es un namedtuple con atributos: product_id, origin, values, etc.
            # rule es el stock.rule record

            # Asegurarse de que procurement_request y sus atributos existen
            if not hasattr(procurement_request, 'product_id') or \
               not hasattr(procurement_request, 'origin') or \
               not hasattr(procurement_request, 'values'):
                _logger.warning(f"[MARBLE-PROCUREMENT] procurement_request con formato inesperado: {procurement_request}. Omitiendo.")
                continue

            product_record = procurement_request.product_id
            origin_str = procurement_request.origin
            values_dict = procurement_request.values or {} # Este es el diccionario con nuestros campos de mármol

            # Si 'marble_sqm' está en los valores y es mayor que 0, guardar los datos
            if 'marble_sqm' in values_dict and values_dict.get('marble_sqm', 0.0) > 0:
                proc_key = f"{product_record.id}_{origin_str}"
                procurement_data_to_apply[proc_key] = {
                    'marble_height': values_dict.get('marble_height', 0.0),
                    'marble_width': values_dict.get('marble_width', 0.0),
                    'marble_sqm': values_dict.get('marble_sqm', 0.0),
                    'lot_general': values_dict.get('lot_general', ''),
                    'marble_thickness': values_dict.get('marble_thickness', 0.0),
                }
                _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 1: Datos de mármol capturados para {product_record.name} (clave {proc_key}): {procurement_data_to_apply[proc_key]}")
            else:
                _logger.debug(f"[MARBLE-PROCUREMENT] BUCLE 1: No se capturaron datos de mármol para {product_record.name} desde origen {origin_str} (values: {values_dict})")

        # Llamar al método padre.
        # Esto creará/actualizará las POs. Durante este proceso, se llamará a nuestro
        # _prepare_purchase_order_line para las nuevas líneas de PO.
        res = super()._run_buy(procurements)

        # BUCLE 2: Encontrar las líneas de PO recién creadas/actualizadas y aplicar/reafirmar los datos de mármol.
        # Esto es importante para asegurar que el valor de marble_sqm persista.
        if procurement_data_to_apply: # Solo si hay datos que aplicar
            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: Iniciando aplicación de datos de mármol a PO Lines. Datos capturados: {procurement_data_to_apply}")
            for procurement_request, rule in procurements: # Iteración corregida
                if not hasattr(procurement_request, 'product_id') or \
                   not hasattr(procurement_request, 'origin') or \
                   not hasattr(procurement_request, 'values'):
                    # Ya se advirtió en el primer bucle si el formato era incorrecto
                    continue

                product_record = procurement_request.product_id
                origin_str = procurement_request.origin
                values_dict = procurement_request.values or {} # Contiene move_dest_ids

                proc_key = f"{product_record.id}_{origin_str}"

                if proc_key in procurement_data_to_apply:
                    marble_data = procurement_data_to_apply[proc_key]
                    move_dest_ids_val = values_dict.get('move_dest_ids')

                    if move_dest_ids_val:
                        actual_move_ids = []
                        if isinstance(move_dest_ids_val, models.BaseModel): # Recordset
                            actual_move_ids = move_dest_ids_val.ids
                        elif isinstance(move_dest_ids_val, (list, tuple)) and all(isinstance(i, int) for i in move_dest_ids_val): # Lista/tupla de IDs
                            actual_move_ids = list(move_dest_ids_val)
                        elif isinstance(move_dest_ids_val, int): # Un solo ID
                            actual_move_ids = [move_dest_ids_val]
                        else:
                            _logger.warning(f"[MARBLE-PROCUREMENT] BUCLE 2: Tipo inesperado para move_dest_ids: {type(move_dest_ids_val)} para proc_key {proc_key}.")
                            continue
                        
                        if not actual_move_ids:
                            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: No hay move_dest_ids concretos para buscar PO lines para proc_key {proc_key}")
                            continue

                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', actual_move_ids)
                        ])

                        if not po_lines:
                            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: No se encontraron líneas de PO para move_dest_ids {actual_move_ids} (proc_key {proc_key})")
                        else:
                            for po_line in po_lines:
                                _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: Actualizando PO line {po_line.id} (Orden: {po_line.order_id.name}, Producto: {po_line.product_id.name}) con: {marble_data}")
                                # Usar with_context para que el compute en purchase.order.line no sobreescriba marble_sqm
                                po_line.with_context(from_procurement=True).write(marble_data)
                                po_line.refresh() # Para que los logs siguientes muestren el valor actualizado
                                _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: PO line {po_line.id} DESPUÉS de actualizar: m²={po_line.marble_sqm}, altura={po_line.marble_height}, ancho={po_line.marble_width}")
                    else:
                        _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: No hay 'move_dest_ids' en values para proc_key {proc_key}. No se pueden encontrar PO lines por esta vía.")
        else:
            _logger.info("[MARBLE-PROCUREMENT] BUCLE 2: No hay datos de mármol capturados para aplicar a PO Lines.")
            
        return res

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        # 'values' aquí es el procurement_request.values
        _logger.info(f"[MARBLE-PREPARE] Iniciando para producto {product_id.name}, PO: {po.name if po else 'Nueva PO'}")
        _logger.info(f"[MARBLE-PREPARE] Values recibidos: {values}")

        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        _logger.info(f"[MARBLE-PREPARE] Valores de res DESPUÉS de super(): {res}")

        marble_fields_to_set = {}
        # Propagar si marble_sqm existe y es mayor a 0 (o cualquier otra condición que consideres)
        if values.get('marble_sqm', 0.0) > 0:
            marble_fields_to_set['marble_sqm'] = values.get('marble_sqm', 0.0)
            marble_fields_to_set['marble_height'] = values.get('marble_height', 0.0)
            marble_fields_to_set['marble_width'] = values.get('marble_width', 0.0)
            marble_fields_to_set['lot_general'] = values.get('lot_general', '')
            marble_fields_to_set['marble_thickness'] = values.get('marble_thickness', 0.0)
            # No necesitas '_marble_sqm_from_sale' aquí, usa el contexto en el write del Bucle 2.

        if marble_fields_to_set:
            _logger.info(f"[MARBLE-PREPARE] Aplicando campos de mármol a res: {marble_fields_to_set}")
            res.update(marble_fields_to_set)
        else:
            _logger.info(f"[MARBLE-PREPARE] No se aplicaron campos de mármol a res (marble_sqm no era > 0 en values o no estaba presente).")

        _logger.info(f"[MARBLE-PREPARE] Valores de res ANTES de return: {res}")
        return res