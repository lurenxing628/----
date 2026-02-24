(function () {
  function getOrCreateFileHint(form, fileInput) {
    if (!form || !fileInput) return null;
    var hint = form.querySelector(".js-file-required-hint");
    if (hint) return hint;
    hint = document.createElement("div");
    hint.className = "error js-file-required-hint";
    hint.setAttribute("role", "alert");
    hint.setAttribute("aria-live", "assertive");
    hint.style.marginTop = "6px";
    hint.style.fontSize = "12px";
    hint.style.display = "none";
    if (fileInput.parentNode) {
      if (fileInput.nextSibling) {
        fileInput.parentNode.insertBefore(hint, fileInput.nextSibling);
      } else {
        fileInput.parentNode.appendChild(hint);
      }
    } else {
      form.appendChild(hint);
    }
    return hint;
  }

  function clearFileHint(form) {
    if (!form) return;
    var hint = form.querySelector(".js-file-required-hint");
    if (!hint) return;
    hint.textContent = "";
    hint.style.display = "none";
  }

  // 轻量级交互：提示用户是否已选择文件
  document.addEventListener("change", function (e) {
    var target = e.target;
    if (!target || !target.matches || !target.matches("input[type='file'][name='file']")) return;
    target.setCustomValidity("");
    target.removeAttribute("aria-invalid");
    target.removeAttribute("title");
    clearFileHint(target.form || target.closest("form"));
  });

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || form.getAttribute("enctype") !== "multipart/form-data") return;

    var fileInput = form.querySelector("input[type='file'][name='file']");
    if (fileInput && !fileInput.value) {
      e.preventDefault();
      var message = "请先选择要上传的 Excel 文件。";
      fileInput.setCustomValidity(message);
      var reported = false;
      if (typeof fileInput.reportValidity === "function") {
        try {
          fileInput.reportValidity();
          reported = true;
        } catch (_e1) {
          reported = false;
        }
      }
      if (!reported) {
        fileInput.setAttribute("aria-invalid", "true");
        fileInput.setAttribute("title", message);
        try {
          fileInput.focus();
        } catch (_e2) {
          // ignore
        }
        var hint = getOrCreateFileHint(form, fileInput);
        if (hint) {
          hint.textContent = message;
          hint.style.display = "block";
        }
      }
    } else {
      clearFileHint(form);
    }
  });
})();

