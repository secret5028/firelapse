from pathlib import Path
p=Path('work/industrial.js');s=p.read_text(encoding='utf-8')
s=s.replace('sprite.scale.set(10,10*c.height/c.width,1);hoseBadge.add(sprite);','sprite.userData.aspect=c.height/c.width;sprite.scale.set(10,10*c.height/c.width,1);hoseBadge.add(sprite);updateHoseSize();')
s=s.replace('function hoseCount(distance)', '''const hoseScreenPoint=new THREE.Vector3();
function updateHoseSize(){const sprite=hoseBadge.children[0];if(!sprite)return;const rect=canvas.getBoundingClientRect();if(rect.height<=0)return;camera.updateMatrixWorld();sprite.getWorldPosition(hoseScreenPoint);hoseScreenPoint.applyMatrix4(camera.matrixWorldInverse);const depth=Math.max(.05,-hoseScreenPoint.z),minPixels=Math.min(400,Math.max(100,rect.width-24)),worldPerPixel=2*depth*Math.tan(camera.fov*Math.PI/360)/rect.height,width=Math.max(10,minPixels*worldPerPixel);sprite.scale.set(width,width*sprite.userData.aspect,1)}
function hoseCount(distance)''')
s=s.replace('animateFlame(t);renderer.render','animateFlame(t);updateHoseSize();renderer.render')
s=s.replace('hoseCount,hoseBadge,','hoseCount,hoseBadge,updateHoseSize,')
p.write_text(s,encoding='utf-8')
