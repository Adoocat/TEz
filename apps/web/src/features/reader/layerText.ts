// A text layer read as text: runs joined, lines separated by one space, words broken at the end
// of a line put together. Every character remembers the text node it came from.

export interface Place {
  node: Text;
  offset: number;
}

export interface LayerText {
  text: string;
  /** Where each character of `text` is; a space made up at a line's end has its line's end. */
  places: Place[];
}

const LINE_HYPHEN = /\p{L}[-­‐]$/u;

export function readLayer(layer: Element): LayerText {
  let text = "";
  const places: Place[] = [];
  const addSpace = (place: Place | undefined) => {
    if (place && text !== "" && !text.endsWith(" ")) {
      text += " ";
      places.push(place);
    }
  };
  const walker = layer.ownerDocument.createTreeWalker(
    layer,
    NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
  );
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node instanceof Element) {
      // pdf.js puts a <br> at the end of each line.
      if (node.tagName !== "BR") continue;
      if (LINE_HYPHEN.test(text)) {
        text = text.slice(0, -1);
        places.pop();
      } else {
        addSpace(places.at(-1));
      }
      continue;
    }
    const { data } = node as Text;
    for (let offset = 0; offset < data.length; offset += 1) {
      const char = data.charAt(offset);
      const place = { node: node as Text, offset };
      if (/\s/.test(char)) addSpace(place);
      else {
        text += char;
        places.push(place);
      }
    }
  }
  return { text, places };
}

/** The part of the layer's text inside a range: from the first character in it to the last. */
export function spanOf({ places }: LayerText, range: Range): { start: number; end: number } | null {
  let start = -1;
  let end = -1;
  places.forEach(({ node, offset }, index) => {
    // After the range's start, and the character itself before its end.
    const inside =
      range.comparePoint(node, offset) === 0 &&
      range.comparePoint(node, Math.min(offset + 1, node.length)) === 0;
    if (!inside) return;
    if (start === -1) start = index;
    end = index + 1;
  });
  return start === -1 ? null : { start, end };
}
