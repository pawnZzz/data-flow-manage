import { describe, it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import { defineComponent } from "vue"

describe("vitest + vue-test-utils 环境", () => {
  it("能挂载并渲染组件", () => {
    const C = defineComponent({ template: "<div class='x'>hi</div>" })
    const w = mount(C)
    expect(w.find(".x").text()).toBe("hi")
  })
})
