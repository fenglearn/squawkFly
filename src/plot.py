#!/usr/bin/python

from time import sleep
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
plt.style.use('ggplot')

# FLAGS
animate_on = True
stack = False

# DATA
with open("output.txt") as datafile:
	data = datafile.read()
	datafile.close()

data = data.split('\n')

all_x = [row.split(' ')[0] for row in data]
all_y = [row.split(' ')[1] for row in data]
all_frames = [row.split(' ')[2] for row in data]

# now translate into frame array
max_frame = int(all_frames[-1])
frame_array = [{} for x in xrange(max_frame+1)]

# for each data point - dump it into the frame of dictionaries
for i in range(0, max_frame+1):
	frame_array[i]["x"] = []
	frame_array[i]["y"] = []

# for each recorded frame
for row in data:	
	x = row.split(' ')[0]
	y = row.split(' ')[1]
	f = int(row.split(' ')[2])

	frame_array[f]["x"].append(x)
	frame_array[f]["y"].append(y)

# frame_array is an array of dictionaries - each containing the dataset for that
# particular frame. The animation need simply update the dataset with the data 
# from that particular frame

# set up the figure, the axis, and the plot element we want to animate
fig = plt.figure()

ax = plt.axes(xlim=(0, 900), ylim=(-600, 0))
ax.set_title("Ball Candidate Centroids", y = 1.03)
ax.set_xlabel("Graphical X")
ax.set_ylabel("Graphical Y")
counter = ax.text(710, -40, 'Frame:', fontsize=15)
scat, = ax.plot([], [], 'ro')


x_set = []
y_set = []

# initialization function: plot the background of each frame
def init():
	scat.set_data([], [])
	return scat,

def animate(i, fig, counter):
	global max_frame
	global x_set
	global y_set

	counter.set_text('Frame: ' + `i`)

	if stack:
		x_set = x_set + frame_array[i]["x"]
		y_set = y_set + frame_array[i]["y"]
	else:
		x_set = frame_array[i]["x"]
		y_set = frame_array[i]["y"]

	scat.set_data(x_set, y_set)

	# re-initialise the datasets to empty for the repeat animation
	if int(i) == int(max_frame-1):
		x_set = []
		y_set = []

	return scat

if animate_on:
	anim = animation.FuncAnimation(fig, animate, fargs=(fig, counter), init_func=init, frames=max_frame, interval=40, blit=False)
	anim.save('animation1.mp4', fps=30, extra_args=['-vcodec', 'libx264'])
else:
	scat.set_data(all_x, all_y)

# start animation
plt.show()