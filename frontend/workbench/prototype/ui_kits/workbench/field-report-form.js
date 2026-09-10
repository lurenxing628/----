(function () {
  const ns=window.APSFieldReports;
  ns.createForm=function ({esc,icon}) {
    const date=(label,name,value)=>'<div class="r-field"><span>'+label+'</span><span data-calendar="'+name+'" data-label="'+label+'"></span><input type="hidden" name="'+name+'" value="'+esc(value)+'"></div>';
    const options=(items,value)=>items.map(v=>'<option'+(v===value?' selected':'')+'>'+esc(v)+'</option>').join('');
    function quantity(value,max) {
      return '<div class="r-field r-quantity-field"><label for="r-qty-input">本次完成数量</label><div class="r-qty-controls">'+
        '<div class="r-stepper"><input id="r-qty-input" name="qty" type="number" inputmode="numeric" min="0" max="'+max+'" step="1" value="'+esc(value)+'" placeholder="待填" aria-describedby="r-qty-preview">'+
        '<div class="r-stepper-arrows"><button type="button" data-qty="up" aria-label="增加 1 件" title="增加 1 件"><span class="r-arrow-up">'+icon('chevron-down')+'</span></button><button type="button" data-qty="down" aria-label="减少 1 件" title="减少 1 件">'+icon('chevron-down')+'</button></div></div>'+
        '<span class="r-caption">件</span><button type="button" class="r-qty-limit" data-qty="min" title="本次完成数量设为 0">最小</button><button type="button" class="r-qty-limit" data-qty="max" title="填入本次最多可报数量">最大</button></div></div>';
    }
    function form(t,r,values) {
      const correction=Boolean(r&&ns.model.complete(r));
      const max=ns.model.quantityLimit(t,r&&r.id),initial=values||{
        qty:r&&r.qty!==null?r.qty:'',start:r?r.start:'',end:r?r.end:'',hours:r&&r.hours!==null?r.hours:'',
        machine:r?r.machine:t.machine,person:r?r.person:t.person,remark:r?r.remark:'',reason:''
      };
      const resource='<div class="r-form-grid r-supplement-grid"><label class="r-field"><span>实际设备</span><select name="machine">'+options(['M-03','M-05','M-07','M-12','M-18'],initial.machine)+'</select></label>'+
        '<label class="r-field"><span>实际人员</span><select name="person">'+options(['张三','李四','王五','赵六','刘七'],initial.person)+'</select></label>'+
        '<label class="r-field r-remark-field"><span>作业备注</span><textarea name="remark" rows="3" placeholder="停顿、交接或其他实际情况">'+esc(initial.remark)+'</textarea></label>'+
        (r?'<label class="r-field" data-reason-field><span>更正原因</span><textarea name="reason" rows="3" placeholder="填写更正原因">'+esc(initial.reason)+'</textarea></label>':'')+'</div>';
      const times=date('实际开工','start',initial.start)+date('本次实际完工','end',initial.end);
      const hours='<label class="r-field"><span>有效工时 (h)</span><input name="hours" type="number" min="0" step="0.1" value="'+esc(initial.hours)+'" placeholder="待填"></label>';
      const core='<div class="r-core-fields"><section class="r-entry-zone r-output-zone" aria-labelledby="r-output-title"><h4 class="r-zone-title" id="r-output-title">产出数量</h4>'+quantity(initial.qty,max)+'<div class="r-zone-note" id="r-qty-preview"></div></section>'+
        '<section class="r-entry-zone r-time-zone" aria-labelledby="r-time-title"><h4 class="r-zone-title" id="r-time-title">实际起止</h4><div class="r-time-fields">'+times+'</div></section>'+
        '<section class="r-entry-zone r-hours-zone" aria-labelledby="r-hours-title"><h4 class="r-zone-title" id="r-hours-title">工时核对</h4>'+hours+'<div class="r-zone-note" id="r-span-preview"></div></section></div>';
      return '<form id="r-report-form" class="r-inline-form" data-mode="'+(correction?'correction':'report')+'">'+core+
        '<details class="r-extra"><summary>'+(correction?'设备 / 人员 / 更正说明':'设备 / 人员 / 备注')+'<span class="r-extra-resource">'+esc(initial.machine)+' / '+esc(initial.person)+'</span></summary>'+resource+'</details>'+
        '<div class="r-form-footer" role="group" aria-label="报工提交">'+
        '<div class="r-form-actions"><button type="button" class="r-action" data-close>取消</button>'+
        (!correction?'<button type="button" class="r-action" data-complete-rest title="带入当前工序剩余件数，并校验实际时间与工时后完工">'+icon('check-check')+'剩余全部完工</button>':'')+
        '<button type="submit" class="r-action primary" data-save>'+icon('check')+(correction?'保存更正':'保存报工')+'</button></div></div><div id="r-error" class="r-error" role="alert" hidden></div></form>';
    }
    return form;
  };
})();
