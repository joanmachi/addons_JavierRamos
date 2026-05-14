
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
import datetime
import math

import logging


_logger = logging.getLogger(__name__)
class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_storable = fields.Boolean(string="Rastrear inventario",default=True)
    parte_conjunto = fields.Boolean(string="¿Es parte de un conjunto?",copy=False)


    largo = fields.Float(string="Largo(L) mm",copy=False)
    ancho = fields.Float(string="Ancho(A) mm",copy=False)
    altura = fields.Float(string="Altura(H) mm",copy=False)
    diametro = fields.Float(string="Diámetro(D) mm",copy=False)
    superficie = fields.Float(string="Superficie(m²)" , digits=(16, 4),copy=False)
    peso = fields.Float(string="Peso(Kg)", digits=(16, 4),copy=False)
    
    
    
    precio_small = fields.Float(string="Precio pequeño")
    min_small = fields.Float(string="Min", digits=(16, 4))
    max_small = fields.Float(string="Max", digits=(16, 4))

    precio_mediano = fields.Float(string="Precio mediano")
    min_mediano = fields.Float(string="Min", digits=(16, 4))
    max_mediano = fields.Float(string="Max", digits=(16, 4))

    precio_grande = fields.Float(string="Precio grande")
    min_grande = fields.Float(string="Min", digits=(16, 4))
    max_grande = fields.Float(string="Max", digits=(16, 4))

    precio_muy_grande = fields.Float(string="Precio muy grande")
    min_muy_grande = fields.Float(string="Min", digits=(16, 4))
    max_muy_grande = fields.Float(string="Max", digits=(16, 4))

    total_precio_componentes = fields.Float(
        string="Total material",
        compute="_compute_total_precio_componentes",
        copy=False
    )


    @api.depends("componentes")
    def _compute_total_precio_componentes(self):
        total = 0
        for componente in self.componentes:
            total += componente.total


        self.total_precio_componentes = total
        
    total_precio_servicio = fields.Float(
        string="Total servicios",
        compute="_compute_total_precio_servicios",
        copy=False
    )

    @api.depends("servicios")
    def _compute_total_precio_servicios(self):
        total = 0
        for componente in self.servicios:
            total += componente.total


        self.total_precio_servicio = total

    total_precio_componentes_unitario = fields.Float(
        string="Total productos",
        compute="_compute_total_precio_componentes_unitario",
        copy=False
    )

    @api.depends("componentes_unitario")
    def _compute_total_precio_componentes_unitario(self):
        total = 0
        for componente in self.componentes_unitario:
            total += componente.total


        self.total_precio_componentes_unitario = total

    total_precio_servicio_conjunto = fields.Float(
        string="Total servicios",
        compute="_compute_total_precio_servicios_conjunto",
        copy=False
    )

    @api.depends("servicios_conjunto")
    def _compute_total_precio_servicios_conjunto(self):
        total = 0
        for componente in self.servicios_conjunto:
            total += componente.precio_unidad


        self.total_precio_servicio_conjunto = total

    total_operaciones = fields.Float(
        string="Total operaciones",
        compute="_compute_total_operaciones",
        copy=False
    )

    @api.depends("fases")
    def _compute_total_operaciones(self):
        
        total_operaciones = 0
        cantidad_producto = 1
    
        for operacion in self.fases:
            tiempo_esperado =  (operacion.minutos * cantidad_producto) / 60
     
            tiempo_preparacion = 0

            tiempo_limpieza = 0
            if not operacion.ignorar_preparacion_limpieza:
                tiempo_preparacion = operacion.centro_trabajo.time_start / 60

                tiempo_limpieza = operacion.centro_trabajo.time_stop / 60

            eficencia = operacion.centro_trabajo.time_efficiency / 100
            coste_hora = operacion.centro_trabajo.costs_hour
            coste_hora = self.get_precio_centro_trabajo(centro_trabajo=operacion.centro_trabajo)
   
   
            coste_operacion = ((tiempo_esperado/eficencia) + tiempo_preparacion + tiempo_limpieza) * coste_hora
            
            total_operaciones = total_operaciones + (coste_operacion  * operacion.num_fases)

        self.total_operaciones = total_operaciones

    @api.depends("total_precio_servicio", "total_precio_componentes", "total_operaciones")
    def _compute_total_cuestionario(self):
        self.total_cuestionario = self.total_precio_servicio + self.total_precio_componentes + self.total_operaciones

    total_cuestionario_conjunto = fields.Float(
        string="Total cuestionario",
        compute="_compute_total_cuestionario_conjunto",
        copy=False
    )

    @api.depends("total_precio_servicio_conjunto", "componentes_unitario")
    def _compute_total_cuestionario_conjunto(self):
        self.total_cuestionario_conjunto = self.total_precio_servicio_conjunto + self.total_precio_componentes_unitario + self.total_operaciones


    total_cuestionario = fields.Float(
        string="Total cuestionario",
        compute="_compute_total_cuestionario",
        copy=False
    )

    @api.depends("total_precio_servicio", "total_precio_componentes", "total_precio_componentes_unitario")
    def _compute_total_cuestionario(self):
        self.total_cuestionario = self.total_precio_servicio + self.total_precio_componentes + self.total_operaciones
    #--------------------------------------------------------------------
    #Calculo total presupuesto
        
    total_cuestionario_presupuesto = fields.Float(
        string="Total linea presupuesto",
        compute="_compute_total_cuestionario_presupuesto",
        copy=False
    )

    @api.depends("total_precio_servicio", "total_precio_componentes", "total_precio_componentes_unitario")
    def _compute_total_cuestionario_presupuesto(self):
        if self.sale_order_line:
            sin_beneficio = (self.calcular_precio_venta(self.sale_order_line.product_uom_qty) * self.sale_order_line.product_uom_qty)
            if self.sale_order_line.order_id.margen_beneficio > 0:
                self.total_cuestionario_presupuesto = sin_beneficio * self.sale_order_line.order_id.margen_beneficio
            else:
                self.total_cuestionario_presupuesto = sin_beneficio
        else:
            self.total_cuestionario_presupuesto = 0

    total_cuestionario_fase_presupuesto = fields.Float(
        string="Total operaciones presupuesto",
        compute="_compute_total_cuestionario_fase_presupuesto",
        copy=False
    )

    @api.depends("total_precio_servicio", "total_precio_componentes", "total_precio_componentes_unitario")
    def _compute_total_cuestionario_fase_presupuesto(self):
        total = 0
        cantidad_producto = 1
        if self.sale_order_line:
            cantidad_producto = self.sale_order_line.product_uom_qty
        total = self.calcular_precio_fases(cantidad_producto=cantidad_producto)
        self.total_cuestionario_fase_presupuesto = total


    total_cuestionario_servicios_presupuesto = fields.Float(
        string="Total servicios presupuesto",
        compute="_compute_total_cuestionario_servicios_presupuesto",
        copy=False
    )

    @api.depends("total_precio_servicio", "total_precio_componentes")
    def _compute_total_cuestionario_servicios_presupuesto(self):
        total = 0
        cantidad_producto = 1
        if self.sale_order_line:
            cantidad_producto = self.sale_order_line.product_uom_qty
        for componente in self.servicios:
            total += (componente.total * cantidad_producto)

        for componente in self.servicios_conjunto:
            coste_componentes += (componente.precio_unidad * cantidad_producto)

            
        self.total_cuestionario_servicios_presupuesto = total

    total_cuestionario_material_presupuesto = fields.Float(
        string="Total material presupuesto",
        compute="_compute_total_cuestionario_material_presupuesto",
        copy=False
    )

    @api.depends("total_precio_servicio", "total_precio_componentes")
    def _compute_total_cuestionario_material_presupuesto(self):
        total = 0
        cantidad_producto = 1
        if self.sale_order_line:
            cantidad_producto = self.sale_order_line.product_uom_qty
        for componente in self.componentes:
            total += (componente.cantidad * cantidad_producto) * componente.precio_unidad
        for componente in self.componentes_unitario:
            if componente.producto.tipo_producto:
                total += (componente.cantidad * cantidad_producto) * componente.precio_unidad
            else:
                total += componente.total
        


        self.total_cuestionario_material_presupuesto = total


    #--------------------------------------------------------------------



    @api.onchange("largo", "ancho", "altura", "diametro", "componentes", "servicios")
    def _onchange_medidas(self):
        _logger.info('--------------- onchange_medidas')
        if self.tipo_producto == 'conjunto':
            return
        superficie = 0
        peso = 0
        peso_materia_prima = 0
        if len(self.componentes) > 0:
            peso_materia_prima = self.componentes[0].producto.weight
        if self.largo and self.ancho and self.altura and self.tipo_producto != 'conjunto':
            _logger.info('------------- if self.largo and self.ancho and self.altura:')
            _logger.info(self.largo)
            _logger.info(self.ancho)
            _logger.info(self.altura)
            
            #Superficie = ((L/1000) x (A/1000) x 2) + ((L/1000) x (H/1000) x 2) + ((A/1000) x (H/1000) x 2) = un dato que seria metros cuadrados
            #Peso = (L/1000) x (A/1000) x H x Peso especifico (este campo debería de ser el campo base de odoo de peso ) = kg de producto
            superficie = ((self.largo/1000) * (self.ancho/1000) * 2) + ((self.largo/1000) * (self.altura/1000) * 2) + ((self.ancho/1000) * (self.altura/1000) * 2)
            peso = (self.largo/1000) * (self.ancho/1000) * self.altura * peso_materia_prima
        elif self.largo and self.diametro:
            _logger.info('------------- elif self.largo and self.diametro:')
            _logger.info(self.largo)
            _logger.info(self.diametro)
            #Superficie = (PI x (radio cuadrado / 1000) x 2) + (2 x PI x (Radio/1000) x L) = metros cuadrados
            #Peso =  PI (3,1416) x (Radio al cuadrado / 1000) x largo/1000 x Peso especifico
            radio_cuadrado = (self.diametro / 2) ** 2
            radio = (self.diametro / 2) 
            superficie = ((math.pi * (radio_cuadrado / 1000) * 2) + (2 * math.pi * (radio/1000) * self.largo) ) / 1000
            peso = math.pi * (radio_cuadrado / 1000) * self.largo/1000 * peso_materia_prima
        _logger.info(superficie)
        _logger.info(peso)
        
        self.write({
            'superficie' : superficie,
            'peso' : peso,
        })
     
        for componente_aux in self.componentes:
            componente_aux.write({
                'cantidad': peso,
                'total': componente_aux.precio_unidad * peso
            })
        for componente_aux in self.servicios:
            precio_servicio = self.calcular_precio_servicio(superficie=superficie, servicio=componente_aux)
            componente_aux.write({
                'precio_unidad': precio_servicio,
                'cantidad': superficie,
                'total': componente_aux.precio_unidad * superficie
            })
        if self.sale_order_line:
            self.calcular_precio_venta()
            self.calcular_fecha_entrega()

    def calcular_precio_servicio(self, superficie, servicio):
        if superficie < servicio.producto.max_small:
            return servicio.producto.precio_small
        if superficie < servicio.producto.max_mediano:
            return servicio.producto.precio_mediano
        if superficie < servicio.producto.max_grande:
            return servicio.producto.precio_grande
        
        return servicio.producto.precio_muy_grande
    margen_beneficio = fields.Float(
        string="Margen de beneficio"
    )
  

    sale_order = fields.Many2one(
        comodel_name='sale.order',
        string="Pedido",
        copy=False
    )
    sale_order_line = fields.Many2one(
        comodel_name='sale.order.line',
        string="Linea pedido",
        copy=False
    )

    tipo_producto = fields.Selection(
        selection= [('unitario', 'Unitario'),('serie', 'Serie'),('conjunto', 'Conjunto')]
        ,copy=False
    )

    componentes = fields.One2many(
        comodel_name="javier_ramos_taller_simple.componentes",
        inverse_name="producto_principal",
        string="Materia prima",
        copy=False
    )
    servicios = fields.One2many(
        comodel_name="javier_ramos_taller_simple.servicios",
        inverse_name="producto_principal",
        string="Servicios subcontratados",
        copy=False
    )
    componentes_unitario = fields.One2many(
        comodel_name="javier_ramos_taller_simple.componentes_unitario",
        inverse_name="producto_principal",
        string="Productos",
        copy=False
    )
    servicios_conjunto = fields.One2many(
        comodel_name="javier_ramos_taller_simple.servicios_conjunto",
        inverse_name="producto_principal",
        string="Servicios subcontratados conjuntos",
        copy=False
    )
    fases = fields.One2many(
        comodel_name="javier_ramos_taller_simple.fases",
        inverse_name="producto_principal",
        string="Operaciones",
        copy=False
    )
    size_producto = fields.Selection([
        ('pequeño', 'PEQUEÑO 100x100x100 mm'),
        ('mediano', 'MEDIANO 300x300x300 mm'),
        ('grande', 'GRANDE 500x900x200 mm'),
        ('muy_grande', 'MUY GRANDE 1000x1200x5-200 mm')
    ], string="Tamaño",
    copy=False)


    def copiar_con_cuestionario(self):


        producto = self
        
        componentes = []
        componentes_unitario = []


        for componente_aux in self.componentes:
            componente = componente_aux.copy()
            componentes.append(componente.id)
        for componente_aux in self.componentes_unitario:
     
            componente = componente_aux.copy()
            componentes_unitario.append(componente.id)
        servicios = []
        servicios_conjunto = []
        for componente_aux in self.servicios:
            componente = componente_aux.copy()
            servicios.append(componente.id)
        for componente_aux in self.servicios_conjunto:
            componente = componente_aux.copy()
            servicios_conjunto.append(componente.id)
     
            
        fases = []
        for fase_aux in self.fases:
            componente = fase_aux.copy()
            fases.append(fase_aux.id)
        producto_nuevo = producto.copy()
            
        producto_nuevo.write({
            'fases' : [(6,0, fases)],
            'componentes' : [(6, 0, componentes)],
            'servicios' : [(6, 0, servicios)],
            'componentes_unitario' : [(6, 0, componentes_unitario)],
            'servicios_conjunto' : [(6, 0, servicios_conjunto)],
            'tipo_producto' : self.tipo_producto,
            'altura': self.altura,
            'largo': self.largo,
            'ancho': self.ancho,
            'diametro': self.diametro,
            'superficie': self.superficie,
            'peso': self.peso,
        })
    def action_abrir_cuestionario(self):

        return {'type': 'ir.actions.act_window',
                'name': 'Cuestionario',
                'res_model': 'javier_ramos_taller_simple.cuestionario',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'producto': self.id, 'modelo_producto': self._name}, }
    
    def action_actualizar_precio(self):
        _logger.info('--------- action_actualizar_precio')
        cantidad_pedido = 0
        if self.sale_order_line:
            cantidad_pedido = self.sale_order_line.product_uom_qty 
        for componente in self.componentes_unitario:
            nuevo_precio_componente = componente.producto.calcular_precio_venta((cantidad_pedido * componente.cantidad))
            _logger.info('nuevo_precio_componente')
            _logger.info(nuevo_precio_componente)
            _logger.info(componente.cantidad)
            _logger.info(nuevo_precio_componente * componente.cantidad)
            componente.write({
                'precio_unidad' : nuevo_precio_componente,
                'total' : nuevo_precio_componente * componente.cantidad,
            })
        nuevo_precio = self.calcular_precio_venta()

        if nuevo_precio > 0 and self.sale_order_line:
            total_fases = 0
            total_servicios = 0
            total_material = 0
            for linea in self.sale_order.order_line:
                if linea.product_template_id:
                    total_fases += linea.product_template_id.total_cuestionario_fase_presupuesto
                    total_servicios += linea.product_template_id.total_cuestionario_servicios_presupuesto
                    total_material += linea.product_template_id.total_cuestionario_material_presupuesto
            self.sale_order.write({
                'total_cuestionario_fase_presupuesto': total_fases,
                'total_cuestionario_servicios_presupuesto': total_servicios,
                'total_cuestionario_material_presupuesto': total_material,
            })

            self.sale_order_line.write({
                'coste_sin_beneficio' : nuevo_precio
            })

            if self.sale_order_line.order_id.margen_beneficio > 0:
                self.sale_order_line.write({
                    'price_unit' : self.sale_order_line.coste_sin_beneficio * self.sale_order_line.order_id.margen_beneficio
                })
                   
            else:
                self.sale_order_line.write({
                    'price_unit' : nuevo_precio
                })
        #self.calcular_fecha_entrega()
        if nuevo_precio:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aviso',
                    'message': 'Coste en venta actualizado',
                    'type': 'success', 
                    'sticky': False    
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aviso',
                    'message': 'No se pudo actualizar el coste en la venta.',
                    'type': 'warning', 
                    'sticky': False    
                }
            }
    
  
    @api.onchange("sale_order_line")
    def onchange_calcular_precio_venta(self):
        _logger.info('--------- onchange_calcular_precio_venta')
        self.calcular_precio_venta()
        #self.calcular_fecha_entrega()

    def calcular_precio_venta(self, cantidad_producto = 0):
        _logger.info('--------- calcular_precio_venta')
        nuevo_precio = 0
        if self.tipo_producto == 'unitario' or self.tipo_producto == 'serie':
            nuevo_precio = self.calcular_precio_venta_unitario_serie(cantidad_producto = cantidad_producto)
        if self.tipo_producto == 'conjunto':
            nuevo_precio = self.calcular_precio_venta_conjunto(cantidad_producto = cantidad_producto)
       
     
        

        return nuevo_precio
    
    def calcular_precio_fases(self, cantidad_producto):
        nuevo_coste = 0
        for operacion in self.fases:
            tiempo_esperado =  (operacion.minutos * cantidad_producto) / 60


            tiempo_preparacion = 0

            tiempo_limpieza = 0
            if not operacion.ignorar_preparacion_limpieza:
                tiempo_preparacion = operacion.centro_trabajo.time_start / 60

                tiempo_limpieza = operacion.centro_trabajo.time_stop / 60

            eficencia = operacion.centro_trabajo.time_efficiency / 100
            coste_hora = operacion.centro_trabajo.costs_hour
            coste_hora = self.get_precio_centro_trabajo(centro_trabajo=operacion.centro_trabajo)
   
            _logger.info(coste_hora)
            coste_operacion = ((tiempo_esperado/eficencia) + tiempo_preparacion + tiempo_limpieza) * coste_hora

            nuevo_coste = nuevo_coste + (coste_operacion  * operacion.num_fases)
        return nuevo_coste
    
    def calcular_precio_venta_unitario_serie(self, cantidad_producto = 0):
        _logger.info('--------- calcular_precio_venta_unitario_serie')
        company = self.env.company
    
        if  cantidad_producto == 0 and self.sale_order_line:
            cantidad_producto = self.sale_order_line.product_uom_qty
        if not cantidad_producto:
            cantidad_producto = 1
 
    
        nuevo_precio = 0
        nuevo_coste = self.calcular_precio_fases(cantidad_producto=cantidad_producto)
        

        coste_componentes = 0
        for componente in self.componentes:
            if componente.producto.tipo_producto and componente.producto != componente.producto_principal:
                coste_componentes += componente.cantidad * componente.producto.calcular_precio_venta((cantidad_producto * componente.cantidad))
            else:
                coste_componentes += componente.total

        for componente in self.servicios:
            coste_componentes += (componente.total * cantidad_producto)
      
        nuevo_precio = 0
        if nuevo_coste > 0 and cantidad_producto > 0:
            nuevo_precio = (nuevo_coste / cantidad_producto) + coste_componentes
   
        return nuevo_precio
    
    def calcular_precio_venta_conjunto(self, cantidad_producto = 0):
        _logger.info('--------- calcular_precio_venta_conjunto')
        company = self.env.company

       
        if cantidad_producto == 0 and self.sale_order_line:
            cantidad_producto = self.sale_order_line.product_uom_qty
        if not cantidad_producto:
            cantidad_producto = 1
    
        nuevo_precio = 0
        nuevo_coste = self.calcular_precio_fases(cantidad_producto=cantidad_producto)
        
        coste_componentes = 0
     
        for componente in self.componentes_unitario:
            if componente.producto.tipo_producto and componente.producto != componente.producto_principal:
                componente.precio_unidad = componente.producto.calcular_precio_venta((cantidad_producto * componente.cantidad))
                coste_componentes += componente.cantidad * componente.precio_unidad
            else:
                coste_componentes += componente.total
    
        for componente in self.servicios_conjunto:
            coste_componentes += (componente.precio_unidad * cantidad_producto)
        nuevo_precio = 0
        if nuevo_coste > 0 and cantidad_producto > 0:
            nuevo_precio = (nuevo_coste / cantidad_producto) + coste_componentes

        return nuevo_precio
    
    def calcular_fecha_entrega(self):
        _logger.info('--------- calcular_fecha_entrega')
        company = self.env.company
        if not self.sale_order_line:
            return False
        
        producto = self.sale_order_line.product_template_id
    
        dias = 0
        minutos_fase = 0
        for operacion in producto.fases:
            minutos_fase = minutos_fase + (operacion.minutos * operacion.num_fases)
        dias_fase = 0
        if minutos_fase > 0:
            if minutos_fase <= 480:
                dias_fase = 1
            if dias_fase == 0:
                dias_aux = minutos_fase / 480
                entero = int(dias_aux)
                decimales = dias_aux - entero
                if decimales > 0:
                    dias_fase = entero + 1
        dias = dias + dias_fase
        dias_componentes = 0
        for componente in producto.componentes:
            if componente.tiempo_recepcion > 0 and componente.tiempo_recepcion > dias_componentes:
                dias_componentes = componente.tiempo_recepcion
        dias = dias + dias_componentes
        dias_componentes = 0
        for componente in producto.componentes_unitario:
            if componente.tiempo_recepcion > 0 and componente.tiempo_recepcion > dias_componentes:
                dias_componentes = componente.tiempo_recepcion
        dias = dias + dias_componentes
        for componente in producto.servicios:
            if componente.tiempo_esperado > 0:
                dias = dias + componente.tiempo_esperado
        for componente in producto.servicios_conjunto:
            if componente.tiempo_esperado > 0:
                dias = dias + componente.tiempo_esperado
 

        fecha_pedido = self.sale_order_line.order_id.date_order
        if dias > 0 and fecha_pedido:
            fecha_entrega = fecha_pedido + datetime.timedelta(days=dias)
            self.sale_order_line.order_id.write({
                'commitment_date' : fecha_entrega
            })

      
            return True

        return False
    
    def get_precio_centro_trabajo(self, centro_trabajo):
        precio = 0
        if precio == 0 and self.largo <= centro_trabajo.small_largo and self.diametro == 0:
            precio = centro_trabajo.small_coste_hora
        if precio == 0 and self.largo <= centro_trabajo.mediano_largo and self.diametro == 0:
            precio = centro_trabajo.mediano_coste_hora
        if precio == 0 and self.largo <= centro_trabajo.grande_largo  and self.diametro == 0:
            precio = centro_trabajo.grande_coste_hora
        if precio == 0 and self.largo > centro_trabajo.grande_largo and self.diametro == 0:
            precio = centro_trabajo.muy_grande_coste_hora

        if precio == 0  and self.diametro <= centro_trabajo.small_diametro:
            precio = centro_trabajo.small_coste_hora
        if precio == 0  and self.diametro <= centro_trabajo.mediano_diametro:
            precio = centro_trabajo.mediano_coste_hora
        if precio == 0  and self.diametro <= centro_trabajo.grande_diametro:
            precio = centro_trabajo.grande_coste_hora
        if precio == 0  and self.diametro > centro_trabajo.grande_diametro:
            precio = centro_trabajo.muy_grande_coste_hora
        

        return precio
