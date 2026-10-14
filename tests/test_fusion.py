from app.services.fusion import rrf_fuse


def test_rrf_order():
    # list1: 1,2,3 | list2: 3,1,4
    result = rrf_fuse([[1, 2, 3], [3, 1, 4]])
    assert [cid for cid, _ in result] == [1, 3, 2, 4]


def test_item_in_both_lists_beats_single_list_item():
    result = dict(rrf_fuse([[10, 20], [30, 10]]))
    assert result[10] > result[20]
    assert result[10] > result[30]


def test_empty_rankings():
    assert rrf_fuse([]) == []