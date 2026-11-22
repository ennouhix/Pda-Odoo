/** Mode caisse simplifié pour un hanout.
 *
 * Le drapeau ``hanout_simple_mode`` de la caisse POS ajoute la classe
 * ``o_hanout_simple`` au document : la feuille de style du module masque
 * alors le pavé quantité/prix/remise, les actions avancées et les boutons
 * client, et agrandit les tuiles produits ainsi que le bouton d'encaissement.
 */
import { patch } from "@web/core/utils/patch";
import { Chrome } from "@point_of_sale/app/pos_app";

patch(Chrome.prototype, {
    setup() {
        super.setup();
        const simple = Boolean(this.pos?.config?.hanout_simple_mode);
        document.body.classList.toggle("o_hanout_simple", simple);
    },
});
