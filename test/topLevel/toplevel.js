#!/usr/bin/env node
// toplevel.js — фиктивные данные для теста .0 (JavaScript)

const fs = require("fs");
const MAX = 12;

const CONFIG = {
  size: "L",
  tags: ["a", "b"],
};

function pack(box) {
  return { box };
}

const ship = (n) => n * 2;

class Box {
  constructor(id) {
    this.id = id;
  }
}

module.exports = { pack, ship, Box };
