import pickle
visited = set()


# Writing to a binary file
with open('visited.pkl', 'wb') as file:
    pickle.dump(visited, file)
