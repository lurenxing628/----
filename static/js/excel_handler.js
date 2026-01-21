(function () {
  // 轻量级交互：提示用户是否已选择文件
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || form.getAttribute("enctype") !== "multipart/form-data") return;

    var fileInput = form.querySelector("input[type='file'][name='file']");
    if (fileInput && !fileInput.value) {
      e.preventDefault();
      alert("请先选择要上传的 Excel 文件。");
    }
  });
})();

