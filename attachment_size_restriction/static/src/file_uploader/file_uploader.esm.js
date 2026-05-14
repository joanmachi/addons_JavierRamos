/** @odoo-module **/

import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {FileUploader} from "@web/views/fields/file_handler";
import {humanSize} from "@web/core/utils/binary";
import {patch} from "@web/core/utils/patch";
import {session} from "@web/session";
import {_t} from "@web/core/l10n/translation"; // eslint-disable-line sort-imports
import {useService} from "@web/core/utils/hooks";

patch(FileUploader.prototype, {
    setup() {
        super.setup();
        this.max_attachment_size = session.max_attachment_size || 10 * 1024 * 1024;
        this.dialogService = useService("dialog");
    },
    /**
     * @inherit
     */
    // eslint-disable-next-line no-unused-vars
    async onFileChange(ev) {
        var larger_files = [];
        for (const file of ev.target.files) {
            if (file.size > this.max_attachment_size) {
                larger_files.push(file);
            }
        }
        // Raise the validation error.
        if (larger_files.length !== 0) {
            this.dialogService.add(ConfirmationDialog, {
                body: _t(
                    "The selected file exceeds the maximum file size of %s",
                    humanSize(this.max_attachment_size)
                ),
                title: _t("Valiation Error"),
            });
            return false;
        }
        return super.onFileChange(...arguments);
    },
});
