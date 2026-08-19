// toplevel.tsx — фиктивные данные для теста .0 (React / TSX)

import React from "react";

export const TITLE = "Fruit Box";

interface Props {
  count: number;
}

// arrow-компонент, привязанный к const (итерация 2: поднять по имени)
export const Badge = ({ count }: Props) => {
  return <span>{count}</span>;
};

export function Label(props: Props): JSX.Element {
  return <b>{props.count}</b>;
}

export default function App() {
  return <Badge count={3} />;
}
