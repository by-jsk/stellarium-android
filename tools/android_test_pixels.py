"""Locate visible controls when Qt's GL surface hides native AX nodes."""

from itertools import groupby

def close_control(image):
    image=image.convert('RGB');width,height=image.size;pixels=image.load()
    left,right=int(width*.88),int(width*.99)
    top,bottom=int(height*.12),int(height*.4)
    remaining={(x,y) for y in range(top,bottom) for x in range(left,right)
               if pixels[x,y][0]>30 and pixels[x,y][1]<7 and pixels[x,y][2]<7}
    candidates=[]
    while remaining:
        start=remaining.pop();component={start};queue=[start]
        while queue:
            x,y=queue.pop()
            for dx,dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                p=(x+dx,y+dy)
                if p in remaining:remaining.remove(p);component.add(p);queue.append(p)
        x0=min(p[0] for p in component);x1=max(p[0] for p in component)
        y0=min(p[1] for p in component);y1=max(p[1] for p in component)
        w,h=x1-x0+1,y1-y0+1
        if not (10<=w<=60 and 10<=h<=60 and .7<w/h<1.4 and len(component)>25):continue
        diagonal=sum(min(abs((x-x0)/(w-1)-(y-y0)/(h-1)),
                         abs((x-x0)/(w-1)+(y-y0)/(h-1)-1))<.19 for x,y in component)/len(component)
        if diagonal>.85:candidates.append((diagonal,(x0+x1)//2,(y0+y1)//2))
    assert len(candidates)==1,f'Expected one visible close X, found {candidates}'
    return candidates[0][1:]


def update_install_control(image):
    """Find the update screen's single wide, labelled button in screenshot pixels."""
    image = image.convert('RGB')
    width, height = image.size
    pixels = image.load()
    panel_sides = [int(width * fraction) for fraction in (.02, .98)]
    button_sides = [int(width * fraction) for fraction in (.12, .20, .26, .74, .80, .88)]

    def shows_button_fill(y):
        panel_left, panel_right = (pixels[x, y] for x in panel_sides)
        fill = [pixels[x, y] for x in button_sides]
        reds = [red for red, _, _ in fill]
        return (abs(panel_left[0] - panel_right[0]) <= 2
                and all(green < 7 and blue < 7 for _, green, blue in fill)
                and max(reds) - min(reds) <= 2
                and min(reds) >= max(panel_left[0], panel_right[0]) + 4)

    candidates = []
    for is_fill, rows in groupby(range(int(height * .18), int(height * .56)), shows_button_fill):
        if not is_fill:
            continue
        band = list(rows)
        if not height // 40 <= len(band) <= height // 8:
            continue
        top, bottom = band[0], band[-1]
        center_y = (top + bottom) // 2
        fill_red = pixels[button_sides[0], center_y][0]
        # Require visible text near the middle, so an empty background block cannot pass.
        label = image.crop((int(width * .28), top + len(band) // 4,
                            int(width * .72), bottom - len(band) // 4))
        ink = sum(red > fill_red + 8 and green < 7 and blue < 7
                  for red, green, blue in label.getdata())
        if ink > 20:
            candidates.append((width // 2, center_y))

    if len(candidates) != 1:
        raise ValueError(f'Expected one visible update install button, found {candidates}')
    return candidates[0]
