
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def plot3D(data_3d, name='3D Plot'):

    all_x = [point[0] for point in data_3d]
    all_y = [point[1] for point in data_3d]
    all_z = [point[2] for point in data_3d]

    fig = plt.figure(name)
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(all_x, all_y, all_z, zdir='z')

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')

    plt.show()


# can provide an optional second set of data
def plot2D(pts1, pts2=[], name='2D Plot'):
    onlyoneset = False
    x1 = [p[0] for p in pts1]
    y1 = [p[1] for p in pts1]

    try:
        x2 = [p[0] for p in pts2]
        y2 = [p[1] for p in pts2]
    except IndexError:
        onlyoneset = True

    fig = plt.figure(name)
    ax = plt.axes()
    # ax = plt.axes(xlim=(0, 1280), ylim=(0, 720))
    ax.scatter(x1, y1, color='r')
    if not onlyoneset:
        ax.scatter(x2, y2, color='b')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')

    plt.show()


def plotEpilines(lines, pts, index):
    name = 'Corresponding Epilines on Image ' + str(index)
    fig = plt.figure(name)
    ax = plt.axes(xlim=(0, 1280), ylim=(0, 720))

    for r in lines:
        a, b, c = r[0], r[1], r[2]
        x = np.linspace(0, 1280, 5)
        y = ((-c) - (a * x)) / b
        ax.plot(x, y)

    x = []
    y = []
    for p in pts:
        x.append(p[0])
        y.append(p[1])

    ax.plot(x, y, 'r.')

    plt.show()


# given a list of numbers, visualise them to spot outliers
def plotOrderedBar(data, name='Indexed Bar', xlabel='X', ylabel='Y'):
    x = []
    y = []
    mean = sum(data) / len(data)

    for i, d in enumerate(data):
        x.append(i)
        y.append(d)

    fig = plt.figure(name)
    ax = plt.axes()
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.bar(x, y)
    ax.axhline(mean)

    plt.show()
