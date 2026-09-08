const NS = 'http://www.w3.org/2000/svg';
const number = new Intl.NumberFormat('en-US');

function svgElement(tag, attributes = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

// A single focusable chart: pointer/touch and arrow keys inspect the same daily data.
export function mountTrend(container, readout, points) {
  let selected = points.length - 1;
  let updateSelection;
  container.tabIndex = 0;
  container.setAttribute('role', 'slider');
  container.setAttribute('aria-label', '查看累计解题曲线的日期');
  container.setAttribute('aria-orientation', 'horizontal');
  container.setAttribute('aria-valuemin', '0');
  container.setAttribute('aria-valuemax', String(points.length - 1));

  function draw() {
    const width = Math.max(200, container.clientWidth);
    const height = 240, left = 48, right = width - 18, top = 20, bottom = height - 32;
    const stepSize = Math.max(1, points.at(-1).total / 4);
    const magnitude = 10 ** Math.floor(Math.log10(stepSize));
    const step = Math.ceil(stepSize / magnitude) * magnitude;
    const ceiling = step * 4;
    const x = index => left + index / Math.max(1, points.length - 1) * (right - left);
    const y = total => bottom - total / ceiling * (bottom - top);
    const svg = svgElement('svg', { viewBox: `0 0 ${width} ${height}`, 'aria-hidden': 'true', focusable: 'false' });
    for (let tick = 0; tick <= 4; tick++) {
      const value = tick * step, position = y(value);
      svg.append(svgElement('line', { x1: left, x2: right, y1: position, y2: position, class: 'trend-grid' }));
      svg.append(svgElement('text', { x: left - 10, y: position + 4, 'text-anchor': 'end', class: 'trend-axis' }, number.format(value)));
    }
    const tickCount = width < 520 ? 3 : 5;
    const sameYear = points[0].day.slice(0, 4) === points.at(-1).day.slice(0, 4);
    for (let tick = 0; tick < tickCount; tick++) {
      const index = Math.round(tick * (points.length - 1) / (tickCount - 1));
      const day = points[index].day;
      const label = sameYear ? `${Number(day.slice(5, 7))}/${Number(day.slice(8))}` : `${day.slice(0, 4)}.${day.slice(5, 7)}`;
      svg.append(svgElement('text', { x: x(index), y: height - 7, 'text-anchor': tick === 0 ? 'start' : tick === tickCount - 1 ? 'end' : 'middle', class: 'trend-axis' }, label));
    }
    const path = points.map((point, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${y(point.total).toFixed(2)}`).join(' ');
    svg.append(svgElement('path', { d: `${path} L${right},${bottom} L${left},${bottom} Z`, class: 'trend-area' }));
    svg.append(svgElement('path', { d: path, class: 'trend-line' }));
    const guide = svgElement('line', { y1: top, y2: bottom, class: 'trend-guide' });
    const dot = svgElement('circle', { r: 5, class: 'trend-dot' });
    svg.append(guide, dot);
    container.replaceChildren(svg);

    updateSelection = index => {
      selected = Math.max(0, Math.min(points.length - 1, index));
      const point = points[selected];
      guide.setAttribute('x1', x(selected)); guide.setAttribute('x2', x(selected));
      dot.setAttribute('cx', x(selected)); dot.setAttribute('cy', y(point.total));
      const label = `${point.day} · 累计 ${number.format(point.total)} 题 · 当日 +${point.added}`;
      readout.textContent = label;
      container.setAttribute('aria-valuenow', String(selected));
      container.setAttribute('aria-valuetext', label);
    };
    updateSelection(selected);
    container.onpointermove = event => {
      if (event.pointerType === 'touch' && !event.buttons) return;
      const position = event.clientX - container.getBoundingClientRect().left;
      updateSelection(Math.round((position - left) / (right - left) * (points.length - 1)));
    };
    container.onpointerdown = container.onpointermove;
  }

  container.onkeydown = event => {
    const offsets = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -30, PageUp: 30 };
    if (event.key in offsets || event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      updateSelection(event.key === 'Home' ? 0 : event.key === 'End' ? points.length - 1 : selected + offsets[event.key]);
    }
  };
  container.onpointerleave = () => { if (document.activeElement !== container) updateSelection(points.length - 1); };
  draw();
  const observer = new ResizeObserver(draw);
  observer.observe(container);
  return () => observer.disconnect();
}
