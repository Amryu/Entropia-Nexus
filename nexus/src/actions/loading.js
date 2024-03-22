import { navigate } from "$lib/util";

export function loading(node) {
  let listener = async (evt) => {
    evt.preventDefault();

    await navigate(evt.currentTarget.href);
  };

  node.addEventListener('click', listener);

  return {
    destroy() {
      node.removeEventListener('click', listener);
    }
  };
}