# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model): # Aunque el archivo se llame procurement_group.py, la clase hereda stock.rule
    _inherit = 'stock.rule'

    def _run_buy(self, procurements):
        _logger.info(f"[MARBLE-PROCUREMENT] Ejecutando _run_buy para {len(procurements)} procurements")

        procurement_data_to_apply = {} # Diccionario para guardar los datos de mármol a aplicar

        # BUCLE 1: Extraer y almacenar los datos de mármol de los procurements
        for proc_tuple in procurements:
            # Estructura esperada de proc_tuple:
            # (product_record, qty, uom_record, location_record, name_str, origin_str, company_record, values_dict)

            # Verificar que la tupla tenga la estructura esperada
            if not (isinstance(proc_tuple, tuple) and len(proc_tuple) >= 8):
                _logger.warning(f"[MARBLE-PROCUREMENT] Se encontró un procurement con formato inesperado: {proc_tuple}. Omitiendo.")
                continue

            product_record = proc_tuple[0]    # Es un recordset de product.product
            origin_str = proc_tuple[5]        # Es el string de origen (ej. SO001)
            values_dict = proc_tuple[7] or {} # Es el diccionario de valores propagados

            # Si 'marble_sqm' está en los valores y es mayor que 0, guardar los datos
            if 'marble_sqm' in values_dict and values_dict.get('marble_sqm', 0.0) > 0:
                # Crear una clave única para este procurement (producto + origen)
                proc_key = f"{product_record.id}_{origin_str}"
                procurement_data_to_apply[proc_key] = {
                    'marble_height': values_dict.get('marble_height', 0.0),
                    'marble_width': values_dict.get('marble_width', 0.0),
                    'marble_sqm': values_dict.get('marble_sqm', 0.0),
                    'lot_general': values_dict.get('lot_general', ''),
                    'marble_thickness': values_dict.get('marble_thickness', 0.0),
                }
                _logger.info(f"[MARBLE-PROCUREMENT] Datos de mármol capturados para {product_record.name} (clave {proc_key}): {procurement_data_to_apply[proc_key]}")
            else:
                _logger.debug(f"[MARBLE-PROCUREMENT] No se capturaron datos de mármol para {product_record.name} desde origen {origin_str} (values: {values_dict})")


        # Llamar al método padre para que Odoo cree/actualice las Órdenes de Compra
        res = super()._run_buy(procurements)

        # BUCLE 2: Encontrar las líneas de PO recién creadas/actualizadas y aplicar los datos de mármol
        for proc_tuple in procurements:
            if not (isinstance(proc_tuple, tuple) and len(proc_tuple) >= 8):
                # Ya se advirtió en el primer bucle
                continue

            product_record = proc_tuple[0]
            origin_str = proc_tuple[5]
            values_dict = proc_tuple[7] or {}

            proc_key = f"{product_record.id}_{origin_str}"

            if proc_key in procurement_data_to_apply:
                marble_data = procurement_data_to_apply[proc_key]

                # Los 'move_dest_ids' en values_dict son los movimientos de stock
                # que se vincularán a las líneas de la orden de compra.
                # Generalmente es un recordset de stock.move.
                move_dest_ids_val = values_dict.get('move_dest_ids')

                if move_dest_ids_val:
                    actual_move_ids = []
                    if isinstance(move_dest_ids_val, models.BaseModel): # Si es un recordset
                        actual_move_ids = move_dest_ids_val.ids
                    elif isinstance(move_dest_ids_val, list) and all(isinstance(i, int) for i in move_dest_ids_val): # Lista de IDs
                        actual_move_ids = move_dest_ids_val
                    elif isinstance(move_dest_ids_val, int): # Un solo ID
                        actual_move_ids = [move_dest_ids_val]
                    else:
                        _logger.warning(f"[MARBLE-PROCUREMENT] Tipo inesperado para move_dest_ids: {type(move_dest_ids_val)} para proc_key {proc_key}. No se pueden actualizar PO lines.")
                        continue
                    
                    if not actual_move_ids:
                        _logger.info(f"[MARBLE-PROCUREMENT] No hay move_dest_ids concretos para buscar PO lines para proc_key {proc_key}")
                        continue

                    # Buscar las líneas de PO que tienen estos movimientos como destino
                    po_lines = self.env['purchase.order.line'].search([
                        ('move_dest_ids', 'in', actual_move_ids)
                    ])

                    if not po_lines:
                        _logger.info(f"[MARBLE-PROCUREMENT] No se encontraron líneas de PO para move_dest_ids {actual_move_ids} (proc_key {proc_key})")

                    for po_line in po_lines:
                        _logger.info(f"[MARBLE-PROCUREMENT] Actualizando PO line {po_line.id} (Orden: {po_line.order_id.name}) con: {marble_data}")
                        # Usar with_context para que el compute en purchase.order.line no sobreescriba marble_sqm
                        po_line.with_context(from_procurement=True).write(marble_data)
                        # Opcional: verificar el valor guardado
                        # po_line.refresh()
                        # _logger.info(f"[MARBLE-PROCUREMENT] PO line {po_line.id} después de actualizar: m²={po_line.marble_sqm}")
                else:
                    _logger.info(f"[MARBLE-PROCUREMENT] No hay 'move_dest_ids' en values para proc_key {proc_key}. No se pueden encontrar PO lines por esta vía.")
            else:
                # Esto es normal si no había datos de mármol para este procurement_key
                pass
                
        return res

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Asegurar que el campo marble_sqm se propague a las líneas de PO nuevas
        Este método ya lo tenías bien, solo lo incluyo por completitud.
        """
        _logger.info(f"[MARBLE-PREPARE] Preparando PO line para {product_id.name}")
        _logger.info(f"[MARBLE-PREPARE] Values completos: {values}")

        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)

        # Propagar TODOS los campos de mármol si existen en values
        # (values aquí es el diccionario 'values' del procurement_tuple[7])
        marble_fields_to_set = {}
        if values.get('marble_sqm', 0.0) > 0: # Condición principal, si hay m2, propagar el resto.
            marble_fields_to_set['marble_sqm'] = values.get('marble_sqm', 0.0)
            marble_fields_to_set['marble_height'] = values.get('marble_height', 0.0)
            marble_fields_to_set['marble_width'] = values.get('marble_width', 0.0)
            marble_fields_to_set['lot_general'] = values.get('lot_general', '')
            marble_fields_to_set['marble_thickness'] = values.get('marble_thickness', 0.0)

        if marble_fields_to_set:
            res.update(marble_fields_to_set)
            _logger.info(f"[MARBLE-PREPARE] Campos de mármol agregados a la línea de PO: {marble_fields_to_set}")

        return res