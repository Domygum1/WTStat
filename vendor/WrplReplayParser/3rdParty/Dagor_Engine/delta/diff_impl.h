// Copyright (C) Gaijin Games KFT.  All rights reserved.
#pragma once

#include <daNet/bitStream.h>
#include <daNet/daNetTypes.h>


namespace net
{

  namespace delta
  {

    inline BitStream diff_impl(const BitStream &buf0, const BitStream &buf1)
    {
      int size0 = buf0.GetNumberOfBytesUsed();
      int size1 = buf1.GetNumberOfBytesUsed();
      int lowerLimit = std::min(size0, size1);
      int upperLimit = std::max(size0, size1);

      BitStream ret(upperLimit);
      for (int i = 0; i < lowerLimit; ++i)
        *(ret.GetData() + i) = *(buf0.GetData() + i) ^ *(buf1.GetData() + i);

      const BitStream &src = size1 < size0 ? buf0 : buf1;
      for (int i = lowerLimit; i < upperLimit; ++i)
        *(ret.GetData() + i) = *(src.GetData() + i);

      ret.SetWriteOffset(BYTES_TO_BITS(upperLimit));
      return ret;
    }

  } // namespace delta

} // namespace net