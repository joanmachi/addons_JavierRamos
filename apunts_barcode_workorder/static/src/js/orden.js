/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export default class OrdenComponent extends Component {
    static components = {  };
    static props = ["orden"];
    static template = "apunts_barcode_workorder.OrdenComponent";

    setup() {
        this.orden = this.props.orden;
        //this.empleados = this.props.empleados;
        console.log(this.orden);
        this.orm = useService('orm');
    }

    get componentClasses() {
        return '';
    }

    get nombreTrabajadores(){
        return this.orden.working_user_ids.length;
        let nombres = ''
        for (let index = 0; index < this.orden.working_user_ids; index++) {
            const usuario = this.orden.working_user_ids[index];
            if(usuario){

                for (let s = 0; s < this.empleados.length; s++) {
                    if(this.empleados[s].id == usuario){
                        return this.empleados[s].name;
                    }
                }
            }
           
            
        }
        return '';
        console.log(this.props.orden);
        
    }

    

   
}
