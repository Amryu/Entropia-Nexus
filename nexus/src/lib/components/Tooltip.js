// @ts-nocheck

export function tooltip(node, { tooltip, payload }) {
  let elementHover = (e) => onElementHover(e, tooltip, payload);
  let elementOut = () => onElementOut(tooltip, payload);
  let elementMove = (e) => onElementMove(e, tooltip);
  let elementClick = (e) => onElementClick(e, tooltip, payload);

  node.addEventListener('mouseover', elementHover);
  node.addEventListener('mousemove', elementMove);
  node.addEventListener('mouseout', elementOut);
  node.addEventListener('click', elementClick);

  return {
    destroy() {
      node.removeEventListener('mouseover', elementHover);
      node.removeEventListener('mousemove', elementMove);
      node.removeEventListener('mouseout', elementOut);
      node.removeEventListener('click', elementClick);
    }
  };
}

function onElementHover(e, tooltip, payload) {
  tooltip.tooltipPos = { x: e.clientX, y: e.clientY - tooltip.element.offsetHeight };
  tooltip.show = true;
  tooltip.dispatch('show', { payload });
}

function onElementOut(tooltip, payload) {
  tooltip.show = false;
  tooltip.dispatch('hide', { payload });
}

function onElementMove(e, tooltip) {
  tooltip.tooltipPos = { x: e.clientX, y: e.clientY - tooltip.element.offsetHeight };
}

function onElementClick(e, tooltip, payload) {
  tooltip.dispatch('elementClick', { button: e.button, payload });
}