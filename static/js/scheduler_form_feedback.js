(function () {
  "use strict";

  function text(value) {
    return value === null || typeof value === "undefined" ? "" : String(value);
  }

  function trim(value) {
    return text(value).trim();
  }

  function isPositiveInteger(value) {
    if (!/^\d+$/.test(trim(value))) return false;
    return parseInt(trim(value), 10) > 0;
  }

  function isFiniteNumber(value) {
    var s = trim(value);
    if (!s) return false;
    var n = Number(s);
    return isFinite(n);
  }

  function isBlank(value) {
    return !trim(value);
  }

  function setFieldError(field, message) {
    if (!field) return;
    var wrap = field.closest ? field.closest(".form-field") : null;
    var err = null;
    if (wrap) {
      err = wrap.querySelector("[data-field-error-for='" + field.name + "']");
      if (!err) err = wrap.querySelector(".aps-field-error");
      wrap.classList.toggle("is-invalid", !!message);
    }
    if (err) err.textContent = message || "";
  }

  function clearFormErrors(form) {
    if (!form) return;
    form.querySelectorAll(".form-field.is-invalid").forEach(function (item) {
      item.classList.remove("is-invalid");
    });
    form.querySelectorAll(".aps-field-error").forEach(function (item) {
      item.textContent = "";
    });
  }

  function validateBatchCreate(form) {
    var ok = true;
    clearFormErrors(form);
    var batchId = form.elements.batch_id;
    var partNo = form.elements.part_no;
    var quantity = form.elements.quantity;
    var dueDate = form.elements.due_date;

    if (!trim(batchId && batchId.value)) {
      setFieldError(batchId, "请填写批次号。");
      ok = false;
    }
    if (!trim(partNo && partNo.value)) {
      setFieldError(partNo, "请选择图号。");
      ok = false;
    }
    if (!isPositiveInteger(quantity && quantity.value)) {
      setFieldError(quantity, "数量必须是大于 0 的整数。");
      ok = false;
    }
    if (trim(dueDate && dueDate.value) && !/^\d{4}-\d{2}-\d{2}$/.test(trim(dueDate.value))) {
      setFieldError(dueDate, "交期格式不正确，请选择日期。");
      ok = false;
    }
    return ok;
  }

  function validateSimpleCreate(form, fields) {
    var ok = true;
    clearFormErrors(form);
    for (var i = 0; i < fields.length; i++) {
      var item = fields[i];
      var field = form.elements[item.name];
      if (!trim(field && field.value)) {
        setFieldError(field, item.message);
        ok = false;
      }
    }
    return ok;
  }

  function firstControlForForm(formId) {
    var controls = document.querySelectorAll("[form]");
    for (var i = 0; i < controls.length; i++) {
      if (controls[i].getAttribute("form") === formId) return controls[i];
    }
    return null;
  }

  function controlInRow(row, formId, name) {
    if (!row) return null;
    var controls = row.querySelectorAll("[form][name]");
    for (var i = 0; i < controls.length; i++) {
      if (controls[i].getAttribute("form") === formId && controls[i].name === name) return controls[i];
    }
    return null;
  }

  function setControlInvalid(control, invalid) {
    if (!control || !control.classList) return;
    control.classList.toggle("aps-invalid-control", !!invalid);
  }

  function setRowError(row, message) {
    if (!row) return;
    var cell = row.querySelector("td:last-child") || row.lastElementChild;
    if (!cell) return;
    var err = cell.querySelector(".aps-row-error");
    if (!err) {
      err = document.createElement("div");
      err.className = "aps-field-error aps-row-error";
      cell.appendChild(err);
    }
    err.textContent = message || "";
    err.classList.toggle("is-hidden", !message);
  }

  function clearRowState(row) {
    if (!row) return;
    row.querySelectorAll(".aps-invalid-control").forEach(function (item) {
      item.classList.remove("aps-invalid-control");
    });
    setRowError(row, "");
  }

  function validateOperationForm(form) {
    var formId = form && form.id ? form.id : "";
    if (formId.indexOf("opform_") !== 0) return true;

    var first = firstControlForForm(formId);
    var row = first && first.closest ? first.closest("tr") : null;
    if (!row) return true;

    clearRowState(row);
    var messages = [];
    var isInternal = row.getAttribute("data-linkage-row") === "1";

    if (isInternal) {
      var setupHours = controlInRow(row, formId, "setup_hours");
      var unitHours = controlInRow(row, formId, "unit_hours");

      if (!isBlank(setupHours && setupHours.value) && (!isFiniteNumber(setupHours.value) || Number(setupHours.value) < 0)) {
        messages.push("换型工时要填 0 或正数");
        setControlInvalid(setupHours, true);
      }
      if (!isBlank(unitHours && unitHours.value) && (!isFiniteNumber(unitHours.value) || Number(unitHours.value) < 0)) {
        messages.push("单件工时要填 0 或正数");
        setControlInvalid(unitHours, true);
      }
    } else {
      var supplier = controlInRow(row, formId, "supplier_id");
      var extDays = controlInRow(row, formId, "ext_days");
      if (supplier && !trim(supplier.value)) {
        messages.push("请选择供应商");
        setControlInvalid(supplier, true);
      }
      if (extDays && !extDays.disabled && (!isFiniteNumber(extDays.value) || Number(extDays.value) <= 0)) {
        messages.push("外协周期要填大于 0 的天数");
        setControlInvalid(extDays, true);
      }
    }

    if (messages.length) {
      setRowError(row, messages.join("；") + "。");
      return false;
    }
    return true;
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.getAttribute) return;

    if (form.id === "batchCreateForm" && !validateBatchCreate(form)) {
      event.preventDefault();
      return;
    }

    var mode = form.getAttribute("data-aps-validate");
    if (mode === "operator-create") {
      if (!validateSimpleCreate(form, [
        { name: "operator_id", message: "请填写工号。" },
        { name: "name", message: "请填写姓名。" }
      ])) {
        event.preventDefault();
      }
      return;
    }

    if (mode === "machine-create") {
      if (!validateSimpleCreate(form, [
        { name: "machine_id", message: "请填写设备编号。" },
        { name: "name", message: "请填写设备名称。" }
      ])) {
        event.preventDefault();
      }
      return;
    }

    if (form.id && form.id.indexOf("opform_") === 0 && !validateOperationForm(form)) {
      event.preventDefault();
    }
  }, true);
})();
