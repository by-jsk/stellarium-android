"""Locate the visibly rendered close X when Qt's GL surface hides native AX nodes."""
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
