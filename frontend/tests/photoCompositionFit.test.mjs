import test from 'node:test'
import assert from 'node:assert/strict'
import { createAutoIssuePhotoComposition, renderIssuePhotoComposition } from '../src/utils/imageComposer.js'

function draws(photos, composition) {
  const result = []
  const ctx = new Proxy({ drawImage: (...args) => result.push(args) }, { get: (obj, key) => obj[key] ?? (() => {}) })
  renderIssuePhotoComposition({ getContext: () => ctx }, photos, composition)
  return result
}
test('one, two and three-photo layouts preserve all image edges at default zoom', () => {
  for (const dimensions of [
    [[300,2400]], [[2400,200]], [[1200,800],[1600,900]],
    [[300,2400],[2400,200]], [[800,1200],[1600,900],[1000,1000]],
    [[1600,900],[1200,800],[2400,200]], [[600,1600],[900,1600],[800,1500]],
  ]) {
    const photos = dimensions.map(([width,height], id) => ({ id, img: { width,height } }))
    const composition = createAutoIssuePhotoComposition(photos)
    const calls = draws(photos, composition)
    assert.equal(calls.length, photos.length)
    for (const [img,x,y,width,height] of calls) {
      const item = composition.items.find(i => photos.find(p => p.id === i.photoId).img === img)
      assert.equal(item.fit, 'contain')
      assert.ok(x >= item.x - .001 && y >= item.y - .001)
      assert.ok(x + width <= item.x + item.w + .001)
      assert.ok(y + height <= item.y + item.h + .001)
      assert.ok(Math.abs(width / height - img.width / img.height) < .001)
    }
  }
})
test('explicit zoom can crop, while old compositions retain cover semantics', () => {
  const photos = [{ id: 1, img: { width: 1600, height: 900 } }]
  const layout = { width: 500, height: 500, items: [{ photoId: 1,x: 0,y: 0,w: 500,h: 500,scale: 1 }] }
  assert.ok(draws(photos, layout)[0][3] > 500)
  layout.items[0].fit = 'contain'
  assert.equal(draws(photos, layout)[0][3], 500)
  layout.items[0].scale = 2
  assert.equal(draws(photos, layout)[0][3], 1000)
})
