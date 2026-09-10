(function () {
  'use strict';
  const h=React.createElement;
  const transferIcons={import:'file-input',export:'file-output',template:'file-down'};
  const readableColors={
    'var(--ui-primary)':'var(--ui-info-text)',
    'var(--ui-danger)':'var(--ui-danger-text)',
    'var(--ui-warning)':'var(--ui-warning-text)',
    'var(--ui-success)':'var(--ui-success-text)',
    'var(--ui-muted)':'var(--ui-info-muted)'
  };
  function iconName(kind){
    if(!transferIcons[kind])throw new Error('Unknown workbench transfer kind: '+kind);
    return transferIcons[kind];
  }
  function TransferIcon({kind}){
    const name=iconName(kind),nodes=window.APSFieldReports.iconNodes[name];
    return h('svg',{className:'lucide wb-transfer-icon','data-wb-icon':name,viewBox:'0 0 24 24',width:16,height:16,fill:'none',stroke:'currentColor',strokeWidth:2,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true},
      nodes.map(([tag,attributes],index)=>h(tag,{...attributes,key:index})));
  }
  function iconMarkup(kind){
    const host=document.createElement('span'),placeholder=document.createElement('i');
    placeholder.dataset.lucide=iconName(kind);host.appendChild(placeholder);
    window.APSFieldReports.paintIcons(host);
    host.firstElementChild.classList.add('wb-transfer-icon');
    host.firstElementChild.dataset.wbIcon=iconName(kind);
    return host.innerHTML;
  }
  function TransferButton({kind,variant='secondary',className='',children,type='button',...props}){
    return h('button',{...props,type,className:'wb-action wb-transfer'+(variant==='primary'?' wb-primary':'')+(className?' '+className:''),'data-wb-transfer':kind},
      h(TransferIcon,{kind}),h('span',{className:'wb-action-label'},children));
  }
  function ControlButton({className='',...props}){
    return h(window.APSDesignSystem_edbc5d.Button,{...props,className:'wb-control'+(className?' '+className:'')});
  }
  function DataMeter({style={},...props}){
    return h(window.APSDesignSystem_edbc5d.Meter,{...props,style:{...style,borderRadius:'var(--wb-radius-control)'}});
  }
  function MetricStrip({children,columns,className='',style={},...props}){
    return h('div',{...props,className:'wb-metrics'+(className?' '+className:''),style:{'--wb-columns':columns||React.Children.count(children)||1,...style}},children);
  }
  function Metric({label,value,unit,helper,badge,tone='neutral',valueColor,className='',valueClassName='',style={},...props}){
    const color=valueColor?{'--wb-metric-color':readableColors[valueColor]||valueColor}:{};
    return h('div',{...props,className:'wb-metric'+(className?' '+className:''),'data-tone':tone,style:{...color,...style}},
      h('div',{className:'wb-metric-heading'},h('span',{className:'wb-metric-label'},label),badge||null),
      h('div',{className:'wb-metric-line'},h('span',{className:'wb-metric-value'+(valueClassName?' '+valueClassName:'')},value),unit?h('span',{className:'wb-metric-unit'},unit):null),
      helper?h('div',{className:'wb-metric-helper'},helper):null);
  }
  function DataTable({className='',...props}){
    return h('div',{className:'wb-table-shell'},h(window.APSDesignSystem_edbc5d.Table,{...props,className:'wb-table'+(className?' '+className:'')}));
  }
  window.APSWorkbenchUI={TransferButton,TransferIcon,iconMarkup,ControlButton,DataMeter,MetricStrip,Metric,DataTable};
})();
