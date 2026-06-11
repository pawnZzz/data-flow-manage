import { it, expect, beforeEach } from "vitest"
import { read, savePos, saveViewport, clear } from "@/components/graph/viewPrefs"

beforeEach(() => localStorage.clear())

it("空时返回空 positions", () => {
  expect(read(1, 7)).toEqual({ positions: {} })
})

it("savePos 往返，key 含 pid+uid", () => {
  savePos(1, 7, "a", { x: 5, y: 6 })
  expect(read(1, 7).positions.a).toEqual({ x: 5, y: 6 })
  expect(localStorage.getItem("graph:1:7")).toBeTruthy()
  expect(read(2, 7).positions.a).toBeUndefined()
})

it("saveViewport 往返且不丢已存位置", () => {
  savePos(1, 7, "a", { x: 1, y: 2 })
  saveViewport(1, 7, { zoom: 1.5, tx: 10, ty: 20 })
  const p = read(1, 7)
  expect(p.viewport).toEqual({ zoom: 1.5, tx: 10, ty: 20 })
  expect(p.positions.a).toEqual({ x: 1, y: 2 })
})

it("clear 清除", () => {
  savePos(1, 7, "a", { x: 1, y: 2 })
  clear(1, 7)
  expect(read(1, 7)).toEqual({ positions: {} })
})

it("坏 JSON 容错返回空", () => {
  localStorage.setItem("graph:1:7", "{bad")
  expect(read(1, 7)).toEqual({ positions: {} })
})
