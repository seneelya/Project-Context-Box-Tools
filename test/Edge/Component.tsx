import React from "react";

/** A tiny React component — a block-bodied const-arrow bound to a name. */
export const Counter = (props: { start: number }) => {
  const [n, setN] = React.useState(props.start);

  // nested block-bodied arrow bound to `increment` -> named, level 2
  const increment = () => {
    setN((v) => v + 1);   // (v) => v+1 is expression-bodied: NOT a block
  };

  return (
    <button onClick={increment} title={`count: ${n}`}>
      {n}
    </button>
  );
};

// plain named function still works alongside
function label(n: number): string {
  return `count is ${n}`;
}
